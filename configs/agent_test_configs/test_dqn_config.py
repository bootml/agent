#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'cnheider'
'''
Description: Config for training
Author: Christian Heider Nielsen
'''
from configs.agent_test_configs.base_test_config import *

CONFIG_NAME = __name__
CONFIG_FILE = __file__

# Exploration
EXPLORATION_EPSILON_START = 1.0
EXPLORATION_EPSILON_END = 0.04
EXPLORATION_EPSILON_DECAY = 400

INITIAL_OBSERVATION_PERIOD = 0
LEARNING_FREQUENCY = 1
REPLAY_MEMORY_SIZE = 10000
MEMORY = U.ReplayBuffer3(REPLAY_MEMORY_SIZE)

BATCH_SIZE = 128
DISCOUNT_FACTOR = 0.999
RENDER_ENVIRONMENT = False
SIGNAL_CLIPPING = True
DOUBLE_DQN = True
SYNC_TARGET_MODEL_FREQUENCY = 1000

# EVALUATION_FUNCTION = lambda Q_state, Q_true_state: (Q_state - Q_true_state).pow(2).mean()

VALUE_ARCH = U.MLP
OPTIMISER_TYPE = torch.optim.RMSprop  # torch.optim.Adam
ENVIRONMENT_NAME = 'CartPole-v0'
# 'LunarLander-v2' #(coord_x, coord_y, vel_x, vel_y, angle,
# angular_vel, l_leg_on_ground, r_leg_on_ground)


# Architecture
VALUE_ARCH_PARAMETERS = {
  'input_size':   None,  # Obtain from environment
  'hidden_layers':[64, 32, 16],
  'output_size':  None,  # Obtain from environment
  'activation':   F.relu,
  'use_bias':     True,
  }
