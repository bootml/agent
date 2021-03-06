#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from itertools import count
from typing import Any, Tuple
from warnings import warn

import torch
from tqdm import tqdm

tqdm.monitor_interval = 0

from utilities.exceptions.exceptions import HasNoEnvError

__author__ = 'cnheider'

from abc import ABC, abstractmethod

import utilities as U


class Agent(ABC):
  '''
All agent should inherit from this class
'''

  # region Private

  def __init__(self, config=None, environment=None, use_cuda=False, verbose=False, *args, **kwargs):
    self._step_i = 0
    self._rollout_i = 0
    self._end_training = False
    self._input_size = None
    self._output_size = None
    self._divide_by_zero_safety = 1e-10
    self._use_cuda = use_cuda
    self._device = torch.device(
        'cuda:0' if torch.cuda.is_available() and self._use_cuda else 'cpu'
        )
    self._environment = environment

    self._verbose = verbose

    self.__defaults__()

    if config:
      self.set_config_attributes(config)

  def __next__(self):
    if self._environment:
      return self._step()
    else:
      raise HasNoEnvError

  def __iter__(self):
    if self._environment:
      self._last_state = None
      return self
    else:
      raise HasNoEnvError

  def __parse_set_attr(self, **kwargs) -> None:
    for k, v in kwargs.items():
      if k.isupper():
        k_lowered = f'_{k.lower()}'
        self.__setattr__(k_lowered, v)
      else:
        self.__setattr__(k, v)

  @staticmethod
  def __check_for_duplicates_in_args(**kwargs) -> None:
    for key, value in kwargs.items():

      occur = 0

      if kwargs.get(key) is not None:
        occur += 1
      else:
        pass

      if key.isupper():
        k_lowered = f'_{key.lower()}'
        if kwargs.get(k_lowered) is not None:
          occur += 1
        else:
          pass
      else:
        k_lowered = f'{key.lstrip("_").upper()}'
        if kwargs.get(k_lowered) is not None:
          occur += 1
        else:
          pass

      if occur > 1:
        warn(f'Config contains hiding duplicates of {key} and {k_lowered}, {occur} times')

  # endregion

  # region Public

  def run(self, environment, render=True, *args, **kwargs) -> None:

    E = count(1)
    E = tqdm(E, leave=False)
    for episode_i in E:
      E.set_description(f'Episode {episode_i}')

      state = environment.reset()

      F = count(1)
      F = tqdm(F, leave=False)
      for frame_i in F:
        F.set_description(f'Frame {frame_i}')

        action = self.sample_action(state)
        state, reward, terminated, info = environment.step(action)
        if render:
          environment.render()

        if terminated:
          break

  def stop_training(self) -> None:
    self._end_training = True

  def build(self, env, device, **kwargs) -> None:
    self._environment = env
    self._infer_input_output_sizes(env)
    self._device = device

    self._build(**kwargs)

  def train(self, *args, **kwargs) -> Tuple[Any, Any]:

    training_start_timestamp = time.time()

    res = self._train(*args, **kwargs)

    time_elapsed = time.time() - training_start_timestamp
    end_message = f'Training done, time elapsed: {time_elapsed // 60:.0f}m {time_elapsed %60:.0f}s'
    print('\n{} {} {}\n'.format('-' * 9, end_message, '-' * 9))

    return res

  def set_config_attributes(self, config, **kwargs) -> None:
    if config:
      config_vars = U.get_upper_vars_of(config)
      self.__check_for_duplicates_in_args(**config_vars)
      self.__parse_set_attr(**config_vars)
    self.__parse_set_attr(**kwargs)

  # endregion

  # region Protected

  def _step(self):
    if self._environment:
      self._last_state = self._environment.react(self.sample_action(self._last_state))
      return
    else:
      raise HasNoEnvError

  def _infer_input_output_sizes(self, env, *args, **kwargs) -> None:
    '''
Tries to infer input and output size from env if either _input_size or _output_size, is None or -1 (int)

:rtype: object
'''
    self._observation_space = env.observation_space
    self._action_space = env.action_space

    if self._input_size is None or self._input_size == -1:
      self._input_size = env.observation_space.shape
    U.sprint(f'\nobservation dimensions: {self._input_size}\n', color='green', bold=True, highlight=True)

    if self._output_size is None or self._output_size == -1:
      if hasattr(env.action_space, 'num_binary_actions'):
        self._output_size = [env.action_space.num_binary_actions]
      elif len(env.action_space.shape) >= 1:
        self._output_size = env.action_space.shape
      else:
        self._output_size = [env.action_space.n]
    U.sprint(f'\naction dimensions: {self._output_size}\n', color='green', bold=True, highlight=True)

  # endregion

  # region Abstract

  @abstractmethod
  def __defaults__(self) -> None:
    raise NotImplementedError

  @abstractmethod
  def evaluate(self, batch, *args, **kwargs) -> Any:
    raise NotImplementedError

  @abstractmethod
  def rollout(self, initial_state, environment, *, train=True, render=False, **kwargs) -> Any:
    raise NotImplementedError

  @abstractmethod
  def load(self, *args, **kwargs) -> None:
    raise NotImplementedError

  @abstractmethod
  def save(self, *args, **kwargs) -> None:
    raise NotImplementedError

  @abstractmethod
  def sample_action(self, state, *args, **kwargs) -> Any:
    raise NotImplementedError

  @abstractmethod
  def update(self, *args, **kwargs) -> None:
    raise NotImplementedError

  @abstractmethod
  def _build(self, **kwargs) -> None:
    raise NotImplementedError

  @abstractmethod
  def _optimise_wrt(self, error, *args, **kwargs) -> None:
    raise NotImplementedError

  @abstractmethod
  def _train(self, *args, **kwargs) -> Tuple[Any, Any]:
    raise NotImplementedError

  # endregion
