#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from pathlib import Path

import torch
import torch.nn.functional as F

import utilities as U
from agents.pg_agent import PGAgent

__author__ = 'cnheider'
'''
Description: Config for training
Author: Christian Heider Nielsen
'''

PROJECT = 'Neodroid'
CONFIG_NAME = __name__
CONFIG_FILE = __file__
VERBOSE = False
USE_LOGGING = True

# Architecture
POLICY_ARCH_PARAMS = U.ConciseArchSpecification(**{
  'input_size':   None,  # Obtain from environment
  'hidden_layers':[32, 16],
  'output_size':  None,  # Obtain from environment
  'activation':   F.relu,
  'use_bias':     True,
  })
POLICY_ARCH = U.CategoricalMLP

AGENT_TYPE = PGAgent

# Environment Related Parameters
CONNECT_TO_RUNNING = True
RENDER_ENVIRONMENT = False
ENVIRONMENT_NAME = 'grd'
SOLVED_REWARD = 0.9
ACTION_MAGNITUDES = 10000

# Epsilon Exploration
EXPLORATION_EPSILON_START = 0.99
EXPLORATION_EPSILON_END = 0.05
EXPLORATION_EPSILON_DECAY = 500

# Training parameters
LOAD_PREVIOUS_MODEL_IF_AVAILABLE = False
DOUBLE_DQN = False
SIGNAL_CLIPPING = False
CLAMP_GRADIENT = False
BATCH_SIZE = 32
LEARNING_FREQUENCY = 4
SYNC_TARGET_MODEL_FREQUENCY = 10000
REPLAY_MEMORY_SIZE = 1000000
INITIAL_OBSERVATION_PERIOD = 10000
DISCOUNT_FACTOR = 0.99
UPDATE_DIFFICULTY_INTERVAL = 1000
ROLLOUTS = 4000
STATE_TYPE = torch.float
VALUE_TYPE = torch.float
ACTION_TYPE = torch.long
EVALUATION_FUNCTION = F.smooth_l1_loss

# Optimiser
OPTIMISER_TYPE = torch.optim.Adam
OPTIMISER_LEARNING_RATE = 0.0025
OPTIMISER_WEIGHT_DECAY = 1e-5
OPTIMISER_ALPHA = 0.9
OPTIMISER_EPSILON = 1e-02
OPTIMISER_MOMENTUM = 0.0

# Paths
PROJECT_DIRECTORY = Path(os.getcwd())
MODEL_DIRECTORY = PROJECT_DIRECTORY / 'models'
CONFIG_DIRECTORY = PROJECT_DIRECTORY / 'configs'
LOG_DIRECTORY = PROJECT_DIRECTORY / 'logs'

# CUDA
USE_CUDA = True
if USE_CUDA:  # If available
  USE_CUDA = torch.cuda.is_available()

# Visualisation
USE_VISDOM = False
START_VISDOM_SERVER = False
VISDOM_SERVER = 'http://localhost'
if not START_VISDOM_SERVER:
  # noinspection PyRedeclaration
  VISDOM_SERVER = 'http://visdom.ml'

# CONSTANTS
MOVING_AVERAGE_WINDOW = 100
SPACER_SIZE = 60
SEED = 6
SAVE_MODEL_INTERVAL = 100
