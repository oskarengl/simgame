# Ecological Simulation Game

A 2D top-down ecological simulation where different types of animals interact with trees, each other, and the environment.

## Features

- **Trees**: Grow fruits that herbivores can eat
- **Herbivores** (Green): Eat fruits from trees
- **Tree Eaters** (Orange): Eat trees directly
- **Carnivores** (Red): Hunt and eat other animals
- **Decomposers** (Purple): Consume dead animal bodies
- **River System**: Flowing river that can carry animals downstream
- **Walls**: Build boundaries to control animal movement
- **Stats Display**: Real-time population and ecosystem statistics

## Installation

1. Install Python 3.7 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## How to Play

### Controls

- **1**: Select Tree tool
- **2**: Select Herbivore tool
- **3**: Select Tree Eater tool
- **4**: Select Carnivore tool
- **5**: Select Decomposer tool
- **6**: Select Wall tool
- **Left Click**: Place selected entity/tool
- **Right Click**: Cancel wall placement

### Gameplay

- Animals will automatically seek food based on their type
- Animals reproduce when well-fed and near a mate
- Animals die when they run out of hunger
- Dead animals become bodies that decomposers can consume
- The river flows and can carry animals downstream
- Use walls to create boundaries and control animal movement

## Ecological Mechanics

- **Food Chain**: Herbivores → Carnivores, Tree Eaters → Carnivores
- **Decomposition**: Dead animals are consumed by decomposers
- **Reproduction**: Animals reproduce when healthy and near mates
- **Natural Selection**: Only well-fed animals survive and reproduce

