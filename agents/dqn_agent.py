#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import matplotlib

from utilities.transformation.extraction import get_screen
from utilities.visualisation.statistics_plot import plot_durations

__author__ = 'cnheider'
from itertools import count

import numpy as np
import torch
import torch.nn.functional as F
from tqdm import tqdm
import matplotlib.pyplot as plt

import utilities as U
from agents.abstract.value_agent import ValueAgent


class DQNAgent(ValueAgent):
  '''

'''

  # region Protected

  def __defaults__(self) -> None:
    self._memory = U.ReplayBuffer3(10000)
    # self._memory = U.PrioritisedReplayMemory(config.REPLAY_MEMORY_SIZE)  # Cuda trouble

    self._use_cuda = False

    self._evaluation_function = F.smooth_l1_loss

    self._value_arch = U.MLP
    self._value_arch_parameters = U.ConciseArchSpecification(**{
      'input_size':   None,  # Obtain from environment
      'hidden_layers':[64, 32, 16],
      'output_size':  None,  # Obtain from environment
      'activation':   F.relu,
      'use_bias':     True,
      })

    self._batch_size = 128

    self._discount_factor = 0.99
    self._learning_frequency = 1
    self._initial_observation_period = 0
    self._sync_target_model_frequency = 1000

    self._state_type = torch.float
    self._value_type = torch.float
    self._action_type = torch.long

    self._use_double_dqn = True
    self._clamp_gradient = False
    self._signal_clipping = True

    self._eps_start = 1.0
    self._eps_end = 0.02
    self._eps_decay = 400

    self._early_stopping_condition = None
    self._target_value_model = None

    self._optimiser_type = torch.optim.RMSprop
    self._optimiser = None
    self._optimiser_alpha = 0.9
    self._optimiser_learning_rate = 0.0025
    self._optimiser_epsilon = 1e-02
    self._optimiser_momentum = 0.0

  def _build(self, **kwargs) -> None:
    self._value_arch_parameters['input_size'] = self._input_size
    self._value_arch_parameters['output_size'] = self._output_size

    value_model = self._value_arch(
      **self._value_arch_parameters
      ).to(self._device)

    target_value_model = self._value_arch(**self._value_arch_parameters).to(self._device)
    target_value_model = U.copy_state(target_value_model, value_model)
    target_value_model.eval()

    optimiser = self._optimiser_type(
      value_model.parameters(),
      lr=self._optimiser_learning_rate,
      eps=self._optimiser_epsilon,
      # alpha=self._optimiser_alpha,
      # momentum=self._optimiser_momentum,
      )

    self._value_model, self._target_value_model, self._optimiser = value_model, target_value_model, optimiser

  def _optimise_wrt(self, error, **kwargs):
    '''

:param error:
:type error:
:return:
'''
    self._optimiser.zero_grad()
    error.backward()
    if self._clamp_gradient:
      for params in self._value_model.parameters():
        params.grad.data.clamp_(-1, 1)
    self._optimiser.step()

  def _sample_model(self, state, **kwargs):
    model_input = U.to_tensor([state], device=self._device, dtype=self._state_type)

    with torch.no_grad():
      action_value_estimates = self._value_model(model_input)
    max_value_action_idx = action_value_estimates.max(1)[1].item()
    return max_value_action_idx

  # region Public

  def evaluate(self, batch, *args, **kwargs):
    '''

:param batch:
:type batch:
:return:
:rtype:
'''
    states = U.to_tensor(batch.state, dtype=self._state_type, device=self._device) \
      .view(-1, *self._input_size)

    action_indices = U.to_tensor(batch.action, dtype=self._action_type, device=self._device) \
      .view(-1, 1)
    true_signals = U.to_tensor(batch.signal, dtype=self._value_type, device=self._device).view(-1, 1)

    non_terminal_mask = U.to_tensor(batch.non_terminal, dtype=torch.uint8, device=self._device)
    nts = [state for (state, non_terminal_mask) in zip(batch.successor_state, batch.non_terminal) if
           non_terminal_mask]
    non_terminal_successors = U.to_tensor(nts, dtype=self._state_type, device=self._device) \
      .view(-1, *self._input_size)

    if not len(non_terminal_successors) > 0:
      return 0  # Nothing to be learned, all states are terminal

    # Calculate Q of successors
    with torch.no_grad():
      Q_successors = self._value_model(non_terminal_successors)
    Q_successors_max_action_indices = Q_successors.max(1)[1].view(-1, 1)
    if self._use_double_dqn:
      with torch.no_grad():
        Q_successors = self._target_value_model(non_terminal_successors)
    Q_max_successor = torch.zeros(
      self._batch_size, dtype=self._value_type, device=self._device
      )
    Q_max_successor[non_terminal_mask] = Q_successors.gather(
      1, Q_successors_max_action_indices
      ).squeeze()

    # Integrate with the true signal
    Q_expected = true_signals + (self._discount_factor * Q_max_successor).view(
      -1, 1
      )

    # Calculate Q of state
    Q_state = self._value_model(states).gather(1, action_indices)

    return self._evaluation_function(Q_state, Q_expected)

  def update(self):
    error = 0
    if self._batch_size < len(self._memory):
      # indices, transitions = self._memory.sample_transitions(self.C.BATCH_SIZE)
      transitions = self._memory.sample_transitions(self._batch_size)

      td_error = self.evaluate(transitions)
      self._optimise_wrt(td_error)

      error = td_error.item()
      # self._memory.batch_update(indices, errors.tolist())  # Cuda trouble

    return error

  def rollout(self, initial_state, environment, render=False, train=True, **kwargs):
    self._rollout_i += 1

    state = initial_state
    episode_signal = 0
    episode_length = 0
    episode_td_error = 0

    T = count(1)
    T = tqdm(T, f'Rollout #{self._rollout_i}', leave=False)

    for t in T:
      self._step_i += 1

      action = self.sample_action(state)
      next_state, signal, terminated, info = environment.step(action)

      if render:
        environment.render()

      if self._signal_clipping:
        signal = np.clip(signal, -1.0, 1.0)

      successor_state = None
      if not terminated:  # If environment terminated then there is no successor state
        successor_state = next_state

      self._memory.add_transition(
        state, action, signal, successor_state, not terminated
        )

      td_error = 0

      if (
        len(self._memory) >= self._batch_size
        and self._step_i > self._initial_observation_period
        and self._step_i % self._learning_frequency == 0
      ):

        td_error = self.update()

        # T.set_description(f'TD error: {td_error}')

      if (
        self._use_double_dqn
        and self._step_i % self._sync_target_model_frequency == 0
      ):
        self._target_value_model = U.copy_state(self._target_value_model, self._value_model)
        if self._verbose:
          T.write('Target Model Synced')

      episode_signal += signal
      episode_td_error += td_error

      if terminated:
        episode_length = t
        break

      state = next_state

    return episode_signal, episode_length, episode_td_error

  def infer(self, state, **kwargs):
    model_input = U.to_tensor([state], device=self._device, dtype=self._state_type)
    with torch.no_grad():
      value = self._value_model(model_input)
    return value

  def step(self, state, env):
    action = self.sample_action(state)
    return action, env.step(action)


def test_cnn_dqn_agent(config):
  import gym

  device = torch.device('cuda' if config.USE_CUDA else 'cpu')

  env = gym.make(config.ENVIRONMENT_NAME).unwrapped
  env.seed(config.SEED)

  is_ipython = 'inline' in matplotlib.get_backend()
  if is_ipython:
    pass

  plt.ion()

  episode_durations = []

  agent = DQNAgent(C)
  agent.build(env, device)

  episodes = tqdm(range(C.ROLLOUTS), leave=False)
  for episode_i in episodes:
    episodes.set_description(f'Episode:{episode_i}')
    env.reset()
    last_screen = U.transform_screen(get_screen(env), device)
    current_screen = U.transform_screen(get_screen(env), device)
    state = current_screen - last_screen

    rollout = tqdm(count(), leave=False)
    for t in rollout:

      action, (_, signal, terminated, *_) = agent.step(state, env)

      last_screen = current_screen
      current_screen = U.transform_screen(get_screen(env), device)

      successor_state = None
      if not terminated:
        successor_state = current_screen - last_screen

      if agent._signal_clipping:
        signal = np.clip(signal, -1.0, 1.0)

      agent._memory.add_transition(state, action, signal, successor_state, not terminated)

      agent.update()
      if terminated:
        episode_durations.append(t + 1)
        plot_durations(episode_durations=episode_durations)
        break

      state = successor_state

  env.render()
  env.close()
  plt.ioff()
  plt.show()


if __name__ == '__main__':
  import configs.agent_test_configs.test_dqn_config as C

  # import configs.cnn_dqn_config as C

  U.test_agent_main(DQNAgent, C)
  # test_cnn_dqn_agent(C)
