#!/usr/bin/env python3
# coding=utf-8
__author__ = 'cnheider'

import time
from itertools import count

import gym
import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable
from torch.distributions import Categorical
from tqdm import tqdm

import utilities as U
from agents.policy_agent import PolicyAgent
from utilities.visualisation.term_plot import term_plot

tqdm.monitor_interval = 0


class PGAgent(PolicyAgent):

  def __local_defaults__(self):

    self._policy_arch = U.CategoricalMLP
    self._accumulated_error = U.to_var([0.0], use_cuda=self._use_cuda)
    self._evaluation_function = torch.nn.CrossEntropyLoss()
    self._trajectory = U.Trajectory()

    self._policy_arch_params = {
      'input_size':    None,  # Obtain from environment
      'hidden_layers': [64, 32, 16],
      'output_size':   None,  # Obtain from environment
      'activation':    F.relu,
      'use_bias':      True
      }

    self._use_cuda_if_available = False
    self._discount_factor = 0.99
    self._use_batched_updates = False
    self._batch_size = 5
    self._pg_entropy_reg = 1e-4
    self._signal_clipping = False

    self._optimiser_learning_rate = 1e-4
    self._optimiser_type = torch.optim.Adam
    self._optimiser_weight_decay = 1e-5

  def __sample_model__(self, state, **kwargs):
    state_var = U.to_var(state, use_cuda=self._use_cuda_if_available, unsqueeze=True)
    probs = self._policy(state_var)
    m = Categorical(probs)
    action = m.sample()
    return action.cpu().data.numpy()[0]

  def build_model(self, env):
    self.infer_input_output_sizes(env)

    self._policy = self.__build_model__()

  def __build_model__(self):

    policy = self._policy_arch(**self._policy_arch_params)

    if self._use_cuda_if_available:
      policy = policy.cuda()

    self.optimiser = self._optimiser_type(policy.parameters(), lr=self._optimiser_learning_rate,
                                          weight_decay=self._optimiser_weight_decay)

    return policy

  def sample_action(self, state, **kwargs):
    state_var = U.to_var(state, use_cuda=self._use_cuda_if_available, unsqueeze=True)
    probs = self._policy(state_var)
    m = Categorical(probs)
    action_sample = m.sample()
    action = action_sample.cpu().data.numpy()[0]
    # action = np.argmax(action)
    return action, m.log_prob(action_sample), U.log_entropy(probs)

  def sample_cont_action(self, state):
    state_var = U.to_var(state, use_cuda=self._use_cuda_if_available, unsqueeze=True)
    mu, sigma_sq = self._policy(state_var)  # requires MultiheadedMLP

    eps = torch.randn(mu.size())
    # calculate the probability
    action = (mu + sigma_sq.sqrt() * Variable(eps).cuda()).data
    prob = U.normal(action, mu, sigma_sq)
    entropy = -0.5 * ((sigma_sq + 2 * U.pi_torch(self._use_cuda_if_available).expand_as(sigma_sq)).log() + 1)

    log_prob = prob.log()
    return action, log_prob, entropy

  def evaluate(self, **kwargs):
    R = 0
    policy_loss = []
    signals = []
    for r in self._trajectory.signals[::-1]:
      R = r + self._discount_factor * R
      signals.insert(0, R)

    signals = U.to_tensor(signals, use_cuda=self._use_cuda_if_available)

    stddev = signals.std()  # + np.finfo(np.float32).eps) for no zero division
    if signals.shape[0] > 1 and stddev > 0:
      signals = (signals - signals.mean()) / stddev
    else:
      return None

    for log_prob, signal, entropy in zip(self._trajectory.log_probs, signals, self._trajectory.entropies):
      policy_loss.append(-log_prob * signal - self._pg_entropy_reg * entropy)

    loss = torch.cat(policy_loss).sum()
    return loss

  def rollout(self, initial_state, environment, render=False, **kwargs):
    self._rollout_i += 1

    episode_signal = 0
    episode_length = 0
    episode_entropy = 0

    state = initial_state

    T = count(1)
    T = tqdm(T, f'Rollout #{self._rollout_i}', leave=False)

    for t in T:
      action, action_log_probs, entropy, *_ = self.sample_action(state)

      state, signal, terminated, info = environment.step(action)

      if self._signal_clipping:
        signal = np.clip(signal, -1.0, 1.0)

      episode_signal += signal
      episode_entropy += entropy.data.cpu().numpy()
      self._trajectory.remember(signal, action_log_probs, entropy)

      if render:
        environment.render()

      if terminated:
        episode_length = t
        break

    error = self.evaluate()
    self._trajectory.forget()
    if error is not None:
      if self._use_batched_updates:
        self._accumulated_error += error
        if self._rollout_i % self._batch_size == 0:
          self.__optimise_wrt__(self._accumulated_error / self._batch_size)
          self._accumulated_error = U.to_var([0.0], use_cuda=self._use_cuda_if_available)
      else:
        self.__optimise_wrt__(error)

    return episode_signal, episode_length, episode_entropy / episode_length

  def __optimise_wrt__(self, loss, **kwargs):
    self.optimiser.zero_grad()
    loss.backward()
    for params in self._policy.parameters():
      params.grad.data.clamp_(-1, 1)
    self.optimiser.step()

  def infer(self, env, render=True):

    for episode_i in count(1):
      print('Episode {}'.format(episode_i))
      state = env.reset()

      for episode_frame_i in count(1):

        action, *_ = self.sample_action(state)
        state, reward, terminated, info = env.step(action)
        if render:
          env.render()

        if terminated:
          break

  def train(self, _environment, rollouts=2000, render=False, render_frequency=100, stat_frequency=100):

    training_start_timestamp = time.time()
    E = range(1, rollouts)
    E = tqdm(E, f'Episode: {1}', leave=True)

    running_length = 0
    running_signal = 0
    running_lengths = []
    running_signals = []
    for episode_i in E:
      initial_state = _environment.reset()

      if episode_i % stat_frequency == 0:
        t_episode = [i for i in range(1, episode_i + 1)]
        term_plot(t_episode,
                  running_signals,
                  'Running Signal',
                  printer=E.write,
                  percent_size=(1, .24))
        term_plot(t_episode, running_lengths, 'Running Lengths', printer=E.write,percent_size=(1, .24))

        E.set_description(f'Episode: {episode_i}, Running length: {running_length}')

      if render and episode_i % render_frequency == 0:
        signal, dur, *stats = self.rollout(initial_state, _environment, render=render)
      else:
        signal, dur, *stats = self.rollout(initial_state, _environment)

      running_length = running_length * 0.99 + dur * 0.01
      running_lengths.append(running_length)
      running_signal = running_signal * 0.99 + signal * 0.01
      running_signals.append(running_signal)

    time_elapsed = time.time() - training_start_timestamp
    end_message = f'Training done, time elapsed: {time_elapsed // 60:.0f}m {time_elapsed %60:.0f}s'
    print('\n{} {} {}\n'.format('-' * 9, end_message, '-' * 9))

    return self._policy, []


def test_pg_agent(config):
  env = gym.make(config.ENVIRONMENT_NAME)
  env.seed(config.SEED)
  torch.manual_seed(config.SEED)

  agent = PGAgent(config)
  agent.build_model(env)

  _trained_model, training_statistics, *_ = agent.train(env, config.MAX_ROLLOUT_LENGTH,
                                                        render=config.RENDER_ENVIRONMENT)
  U.save_model(_trained_model, config)

  env.close()


if __name__ == '__main__':
  import argparse
  import configs.pg_config as C

  parser = argparse.ArgumentParser(description='PG Agent')
  parser.add_argument('--ENVIRONMENT_NAME', '-E', type=str, default=C.ENVIRONMENT_NAME,
                      metavar='ENVIRONMENT_NAME',
                      help='name of the environment to run')
  parser.add_argument('--PRETRAINED_PATH', '-T', metavar='PATH', type=str, default='',
                      help='path of pre-trained model')
  parser.add_argument('--RENDER_ENVIRONMENT', '-R', action='store_true',
                      default=C.RENDER_ENVIRONMENT,
                      help='render the environment')
  parser.add_argument('--NUM_WORKERS', '-N', type=int, default=4, metavar='NUM_WORKERS',
                      help='number of threads for agent (default: 4)')
  parser.add_argument('--SEED', '-S', type=int, default=1, metavar='SEED',
                      help='random seed (default: 1)')
  parser.add_argument('--skip_confirmation', '-skip', action='store_true',
                      default=False,
                      help='Skip confirmation of config to be used')
  args = parser.parse_args()

  for k, arg in args.__dict__.items():
    setattr(C, k, arg)

  print(f'Using config: {C}')
  if not args.skip_confirmation:
    for k, arg in U.get_upper_vars_of(C).items():
      print(f'{k} = {arg}')
    input('\nPress any key to begin... ')

  try:
    test_pg_agent(C)
  except KeyboardInterrupt:
    print('Stopping')

  torch.cuda.empty_cache()
