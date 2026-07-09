import pygame
import math
import random
from enum import Enum
from typing import List, Optional, Tuple

# Initialize Pygame
pygame.init()

# Constants
INITIAL_WINDOW_WIDTH = 1200
INITIAL_WINDOW_HEIGHT = 800
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
DARK_GREEN = (0, 100, 0)
BROWN = (139, 69, 19)
BLUE = (0, 100, 255)
LIGHT_BLUE = (173, 216, 230)
RED = (255, 0, 0)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)

class AnimalType(Enum):
    HERBIVORE = "herbivore"  # Eats fruits
    TREE_EATER = "tree_eater"  # Eats trees
    CARNIVORE = "carnivore"  # Eats other animals
    DECOMPOSER = "decomposer"  # Eats dead bodies
    ALPHA_PREDATOR = "alpha_predator"  # Eats all animals

class Entity:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.alive = True
    
    def distance_to(self, other: 'Entity') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

class Tree(Entity):
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.size = random.uniform(20, 40)
        self.health = 100
        self.max_health = 100
        self.fruit_count = 0
        self.fruit_capacity = 5
        self.fruit_growth_rate = 0.01  # Probability per frame to grow a fruit
        self.age = 0
        self.last_fertilization = 0  # Frames since last fertilization
        # Herbivore lifetime: hunger starts at 50, decreases 0.05/frame = 1000 frames
        # 5x lifetime = 5000 frames
        self.max_fertilization_time = 5000
        self.fertilization_radius = 40  # Radius to detect poop and dead trees
        
        # Random green shade based on size (smaller trees = lighter green)
        # Size ranges from 20-40, so normalize to 0-1
        size_normalized = (self.size - 20) / 20  # 0 for small (20), 1 for large (40)
        # Larger trees get darker green, smaller trees get lighter green
        # Base green: (0, 150, 0) for large, lighter for small
        green_intensity = int(100 + size_normalized * 100)  # 100-200 range
        self.color = (0, green_intensity, 0)  # Random shade of green
    
    def update(self, seeds: List['Seed'], dead_bodies: List['DeadBody'], dead_trees: List['Tree']):
        self.age += 1
        self.last_fertilization += 1
        
        # Check for nearby fertilization sources (seeds/poop or dead trees)
        fertilization_found = False
        
        # Check for seeds/poop nearby
        for seed in seeds:
            if seed.alive:
                dist = self.distance_to(seed)
                if dist < self.fertilization_radius:
                    # Seed will fertilize in its own update, but we note it's nearby
                    fertilization_found = True
                    self.last_fertilization = 0
                    break
        
        # Check for dead trees nearby
        if not fertilization_found:
            for dead_tree in dead_trees:
                if not dead_tree.alive:
                    dist = self.distance_to(dead_tree)
                    if dist < self.fertilization_radius:
                        self.last_fertilization = 0
                        fertilization_found = True
                        break
        
        # Die if not fertilized for too long
        if self.last_fertilization >= self.max_fertilization_time:
            self.alive = False
            return
        
        # Grow fruits occasionally
        if self.fruit_count < self.fruit_capacity and random.random() < self.fruit_growth_rate:
            self.fruit_count += 1
    
    def take_damage(self, amount: float):
        self.health -= amount
        if self.health <= 0:
            self.alive = False
            self.death_reason = "eaten"
    
    def remove_fruit(self) -> bool:
        if self.fruit_count > 0:
            self.fruit_count -= 1
            return True
        return False
    
    def draw(self, screen: pygame.Surface):
        # Draw trunk
        trunk_width = max(3, int(self.size / 8))
        pygame.draw.rect(screen, BROWN, 
                        (int(self.x - trunk_width/2), int(self.y), trunk_width, int(self.size/2)))
        # Draw foliage with random green shade
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.size/2))
        # Draw fruits as visible yellow/orange circles - make them very visible
        if self.fruit_count > 0:
            fruit_angle = 0
            fruit_spacing = 2 * math.pi / max(1, self.fruit_count)  # Space fruits evenly
            for i in range(self.fruit_count):
                # Position fruits around the tree crown edge
                fruit_radius = self.size/2 - 6  # Position fruits near edge of crown
                fruit_x = self.x + math.cos(fruit_angle) * fruit_radius
                fruit_y = self.y + math.sin(fruit_angle) * fruit_radius
                # Draw fruit with bright orange, larger and more visible
                pygame.draw.circle(screen, ORANGE, (int(fruit_x), int(fruit_y)), 5)
                # Add a bright yellow highlight
                pygame.draw.circle(screen, YELLOW, (int(fruit_x), int(fruit_y)), 3)
                # Add a small white highlight for extra visibility
                pygame.draw.circle(screen, (255, 255, 200), (int(fruit_x - 1), int(fruit_y - 1)), 1)
                fruit_angle += fruit_spacing

class Seed(Entity):
    """Seeds/poop dropped by herbivores, can be eaten by decomposers or fertilize trees"""
    def __init__(self, x: float, y: float, from_fruit: bool = False, is_big_poop: bool = False):
        super().__init__(x, y)
        self.size = 4 if not is_big_poop else 8  # Big poop is larger
        self.fertilization_radius = 30  # Radius for fertilizing trees
        self.from_fruit = from_fruit  # True if this seed came from eating fruit
        self.is_big_poop = is_big_poop  # True if this is big poop from alpha predator (requires 2 decomposers)
        self.decomposers_on_poop = 0  # Track how many decomposers are working on this big poop
        self.growth_timer = 0
        self.growth_interval = 600  # Time before seed can grow into tree
        self.can_grow_tree = False
    
    def update(self, trees: List['Tree']):
        # Clear decomposers_working set each frame for big poop (prevents glitching)
        if hasattr(self, 'is_big_poop') and self.is_big_poop:
            if hasattr(self, 'decomposers_working'):
                self.decomposers_working.clear()
        
        # Seeds don't decay on their own, but can fertilize trees
        # Check if near a tree for fertilization
        for tree in trees:
            if tree.alive:
                dist = self.distance_to(tree)
                if dist < self.fertilization_radius:
                    # Fertilize the tree and disappear
                    tree.last_fertilization = 0  # Reset fertilization timer
                    self.alive = False
                    break
        
        # If seed came from fruit, it has a chance to grow into a tree
        # Check if attribute exists (for backwards compatibility with old seeds)
        if hasattr(self, 'from_fruit') and self.from_fruit:
            if not hasattr(self, 'growth_timer'):
                self.growth_timer = 0
                self.growth_interval = 600
            self.growth_timer += 1
            if self.growth_timer >= self.growth_interval:
                # 1 in 5 chance to grow into a tree
                if random.random() < 0.2:  # 20% = 1/5
                    self.can_grow_tree = True
                    self.growth_timer = 0  # Reset timer
    
    def draw(self, screen: pygame.Surface):
        # Draw as brown circle (larger if big poop)
        color = BROWN if not self.is_big_poop else (101, 67, 33)  # Darker brown for big poop
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.size)
        # Draw indicator for big poop
        if self.is_big_poop:
            pygame.draw.circle(screen, (139, 69, 19), (int(self.x), int(self.y)), self.size + 2, 2)

class DeadBody(Entity):
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.decay_time = 300  # Frames until it disappears (only if decomposer doesn't come)
        self.size = 8
        self.stink_radius = 10  # Starts small
        self.max_stink_radius = 50  # 5x the size
        self.stink_growth_rate = 0.01  # Grows over time (much slower)
        self.being_decomposed = False
    
    def update(self):
        # Only decay if being decomposed, otherwise stay forever
        if self.being_decomposed:
            self.decay_time -= 1
            if self.decay_time <= 0:
                self.alive = False
        else:
            # Grow stink radius
            if self.stink_radius < self.max_stink_radius:
                self.stink_radius += self.stink_growth_rate
    
    def draw(self, screen: pygame.Surface, draw_stink: bool = True):
        alpha = min(255, int(255 * (self.decay_time / 300)) if self.being_decomposed else 200)
        color = (alpha // 2, alpha // 2, alpha // 2)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.size)
        
        # Draw stink radius (semi-transparent)
        if draw_stink and not self.being_decomposed:
            stink_alpha = 30
            stink_surface = pygame.Surface((int(self.stink_radius * 2), int(self.stink_radius * 2)), pygame.SRCALPHA)
            pygame.draw.circle(stink_surface, (100, 50, 50, stink_alpha), 
                             (int(self.stink_radius), int(self.stink_radius)), int(self.stink_radius))
            screen.blit(stink_surface, (int(self.x - self.stink_radius), int(self.y - self.stink_radius)))

class Animal(Entity):
    def __init__(self, x: float, y: float, animal_type: AnimalType):
        super().__init__(x, y)
        self.type = animal_type
        self.size = 8
        self.health = 100
        self.max_health = 100
        self.speed = random.uniform(0.5, 1.5)
        self.angle = random.uniform(0, 2 * math.pi)
        self.reproduction_cooldown = 0
        self.reproduction_threshold = 200  # Frames
        self.in_river = False
        self.river_carried_time = 0
        self.max_river_carry_time = 120  # Frames
        self.in_mud = False  # Track if animal is in mud puddle
        self.on_tree = False  # Track if herbivore is hiding in a tree
        self.being_chased = False  # Track if herbivore is being chased by predator
        
        # Mating system
        self.mating = False
        self.mating_timer = 0
        self.mating_duration = 60  # Frames to complete mating
        self.mating_partner = None
        self.mating_radius = 40  # Radius to find mate (increased from 25 to 40 for easier mating)
        
        # Roaming/idle behavior
        self.idle_timer = 0
        self.idle_duration = 0  # How long to stay idle (0 = not idle)
        self.is_idle = False
        
        # Seed carrying (for herbivores) - max 5 seeds
        self.carried_seeds = 0
        self.max_carried_seeds = 5
        self.seed_drop_timer = 0
        self.seed_drop_interval = 180  # Drop seed after this many frames
        self.seed_growth_timer = 0
        self.seed_growth_interval = 300  # Seeds grow into trees after this many frames (reduced from 600)
        
        # Hibernation (for carnivores)
        self.hibernating = False
        self.hibernation_cave = None
        self.hibernation_threshold = 0.8  # Enter hibernation when health > 80%
        self.hibernation_exit_threshold = 0.3  # Exit when health < 30%
        self.just_entered_hibernation = False
        self.just_exited_hibernation = False
        self.fight_occurred = False
        
        # Type-specific properties
        if animal_type == AnimalType.HERBIVORE:
            self.color = GREEN
            self.view_range = 80
        elif animal_type == AnimalType.TREE_EATER:
            self.color = ORANGE
            self.view_range = 60
            # Tree eaters can carry seeds (like herbivores)
            self.carried_seeds = 0
            self.max_carried_seeds = 5
            self.poop_timer = 0
        elif animal_type == AnimalType.CARNIVORE:
            self.color = RED
            self.view_range = 100
            self.speed *= 1.2  # Carnivores are faster
            self.attempted_kills = {}  # Track which prey we've attempted to kill (resets when leaving radius)
        elif animal_type == AnimalType.DECOMPOSER:
            self.color = PURPLE
            self.view_range = 70
            self.sniff_range = 200  # Much longer range to "sniff" decaying things from far away
        elif animal_type == AnimalType.ALPHA_PREDATOR:
            self.color = (139, 0, 0)  # Dark red
            self.view_range = 150
            self.speed *= 1.5  # Alpha predators are very fast
            self.size = 12  # Larger
            self.attempted_kills = {}  # Track which prey we've attempted to kill (resets when leaving radius)
    
    def update(self, trees: List[Tree], animals: List['Animal'], dead_bodies: List[DeadBody],
               river_segments: List['RiverSegment'], walls: List['Wall'], seeds: List['Seed'],
               spatial_grid: 'SpatialGrid' = None, mud_puddles: List['MudPuddle'] = None,
               window_width: int = 1200, window_height: int = 800):
        if not self.alive:
            return
        
        # Handle health decay for carnivores (hibernation disabled)
        if self.type == AnimalType.CARNIVORE:
            # Normal health decay (slower - they last longer without a meal)
            # Only decay if not already at 0 (prevents issues with speed multiplier)
            if self.health > 0:
                self.health -= 0.03  # Reduced from 0.08 to 0.03 (slower decay)
                # Ensure health doesn't go below 0 (death is handled when health <= 0)
                if self.health < 0:
                    self.health = 0
        elif self.type == AnimalType.ALPHA_PREDATOR:
            # Alpha predators also have health decay
            self.health -= 0.06  # Slightly slower than regular carnivores
            # Ensure health doesn't go below 0 (death is handled when health <= 0)
            if self.health < 0:
                self.health = 0
        elif self.type == AnimalType.DECOMPOSER:
            # Decomposers have 50% faster health decay (shorter lifespan)
            self.health -= 0.075  # 50% more than 0.05 (0.05 * 1.5 = 0.075)
            # Ensure health doesn't go below 0
            if self.health < 0:
                self.health = 0
        else:
            # Other animals slowly lose health over time (like hunger)
            self.health -= 0.05
            # Ensure health doesn't go below 0
            if self.health < 0:
                self.health = 0
        
        self.reproduction_cooldown += 1
        
        # Handle seed dropping and growth for herbivores
        if self.type == AnimalType.HERBIVORE and self.carried_seeds > 0:
            self.seed_drop_timer += 1
            
            # Drop a seed after interval (for decomposers to eat)
            if self.seed_drop_timer >= self.seed_drop_interval:
                # Drop a seed - if carrying seeds, they came from eating fruit
                from_fruit = True  # Seeds carried by herbivores come from eating fruit
                seed = Seed(self.x, self.y, from_fruit=from_fruit)
                seeds.append(seed)
                seed.tracked_creation = True  # Mark for tracking
                seed.tracked_dispersed = True  # Mark as dispersed
                self.carried_seeds -= 1
                self.seed_drop_timer = 0
        
        # Check for stink from dead bodies (affects health) - optimized
        if spatial_grid:
            nearby_bodies = spatial_grid.get_nearby(self.x, self.y, 60)  # Max stink radius
            nearby_bodies = [b for b in nearby_bodies if isinstance(b, DeadBody) and 
                           b.alive and not b.being_decomposed]
        else:
            nearby_bodies = [b for b in dead_bodies if b.alive and not b.being_decomposed]
        
        for body in nearby_bodies:
            dx = body.x - self.x
            dy = body.y - self.y
            dist_sq = dx*dx + dy*dy
            stink_radius_sq = body.stink_radius * body.stink_radius
            if dist_sq < stink_radius_sq:
                dist = math.sqrt(dist_sq)
                # Lose health based on proximity to stink (reduced damage to prevent rapid death)
                damage = 0.05 * (1 - dist / body.stink_radius)  # Reduced from 0.1 to 0.05
                self.health -= damage
                # Ensure health doesn't go below 0
                if self.health < 0:
                    self.health = 0
        
        # Die ONLY when health/hunger runs out - no other causes
        # IMPORTANT: This is the ONLY place where animals die from health depletion
        # Animals can also die from being eaten (in try_eat method), but that's the only other way
        
        # Safety check: ensure health is never negative
        if self.health < 0:
            self.health = 0
        
        # All animals die only when health reaches 0
        if self.health <= 0:
            self.alive = False
            return
        
        # Check if in river
        self.check_river(river_segments)
        
        # Check if in mud
        if mud_puddles:
            self.check_mud(mud_puddles)
        
        # Check if herbivore is on a tree (for hiding from predators)
        if self.type == AnimalType.HERBIVORE:
            self.on_tree = False
            for tree in trees:
                if tree.alive:
                    dx = self.x - tree.x
                    dy = self.y - tree.y
                    dist_sq = dx*dx + dy*dy
                    tree_crown_radius = tree.size / 2
                    if dist_sq < tree_crown_radius * tree_crown_radius:
                        self.on_tree = True
                        break
        
        # Check for predator fights (carnivores and alpha predators fight each other)
        if self.type == AnimalType.CARNIVORE or self.type == AnimalType.ALPHA_PREDATOR:
            self.check_predator_fights(animals, spatial_grid)
        
        # Move
        self.move(trees, animals, dead_bodies, walls, seeds, spatial_grid, window_width, window_height)
        
        # Try to eat
        self.try_eat(trees, animals, dead_bodies, seeds, spatial_grid)
        
        # Handle mating
        if self.mating:
            self.mating_timer += 1
            # Check if partner is still nearby and alive
            if (self.mating_partner is None or not self.mating_partner.alive or 
                self.distance_to(self.mating_partner) > self.mating_radius * 2):
                # Mating interrupted
                self.mating = False
                self.mating_timer = 0
                self.mating_partner = None
            elif self.mating_timer >= self.mating_duration:
                # Mating complete - chance to have offspring
                if random.random() < 0.7:  # 70% chance of successful mating
                    num_offspring = random.randint(1, 3)  # 1-3 offspring
                    for _ in range(num_offspring):
                        offspring = Animal(
                            self.x + random.uniform(-10, 10),
                            self.y + random.uniform(-10, 10),
                            self.type
                        )
                        animals.append(offspring)
                
                # Reset mating state
                self.mating = False
                self.mating_timer = 0
                if self.mating_partner:
                    self.mating_partner.mating = False
                    self.mating_partner.mating_timer = 0
                    self.mating_partner.mating_partner = None
                self.mating_partner = None
                self.reproduction_cooldown = 0
        
        # Try to start mating (all animals need to mate to reproduce)
        if not self.mating and self.reproduction_cooldown > self.reproduction_threshold:
            # Check if healthy enough to mate
            # All animals can mate when health is above 80%
            can_mate = self.health >= self.max_health * 0.8
            
            if can_mate:
                self.try_start_mating(animals, spatial_grid)
    
    def check_river(self, river_segments: List['RiverSegment']):
        self.in_river = False
        for segment in river_segments:
            if segment.contains_point(self.x, self.y):
                self.in_river = True
                self.river_carried_time += 1
                # Move with river flow - much stronger now
                river_force = 2.0  # Increased from 0.3 to make it actually drag animals
                self.x += segment.flow_x * river_force
                self.y += segment.flow_y * river_force
                # Occasionally get caught on beach
                if self.river_carried_time > self.max_river_carry_time:
                    if random.random() < 0.02:  # 2% chance per frame to escape
                        # Move to nearest edge
                        self.x += random.uniform(-20, 20)
                        self.y += random.uniform(-20, 20)
                        self.river_carried_time = 0
                break
        else:
            self.river_carried_time = 0
    
    def check_mud(self, mud_puddles: List['MudPuddle']):
        """Check if animal is in a mud puddle"""
        self.in_mud = False
        if mud_puddles:
            for puddle in mud_puddles:
                if puddle.contains_point(self.x, self.y):
                    self.in_mud = True
                    break
    
    def check_predator_fights(self, animals: List['Animal'], spatial_grid: 'SpatialGrid' = None):
        """Carnivores and alpha predators sometimes fight each other to the death"""
        if not self.alive:
            return
        
        fight_chance = 0.15  # 15% chance per frame when close to another predator
        
        # Use spatial grid for efficient queries
        if spatial_grid:
            nearby_animals = spatial_grid.get_nearby(self.x, self.y, 15)
            nearby_animals = [a for a in nearby_animals if 
                             isinstance(a, Animal) and a != self and a.alive and
                             (a.type == AnimalType.CARNIVORE or a.type == AnimalType.ALPHA_PREDATOR)]
        else:
            nearby_animals = [a for a in animals if 
                             a != self and a.alive and
                             (a.type == AnimalType.CARNIVORE or a.type == AnimalType.ALPHA_PREDATOR)]
        
        for animal in nearby_animals:
            dx = animal.x - self.x
            dy = animal.y - self.y
            dist_sq = dx*dx + dy*dy
            # If very close (within 15 pixels)
            if dist_sq < 225:  # 15*15
                # Chance to start a fight
                if random.random() < fight_chance:
                    # Fight - both take damage, but only die if health reaches 0
                    # Only fight if both animals are still alive and have health > 0
                    if not self.alive or not animal.alive or self.health <= 0 or animal.health <= 0:
                        break
                    
                    damage_per_frame = 1.0  # Reduced from 2.0 to 1.0 (less lethal)
                    self.health -= damage_per_frame
                    animal.health -= damage_per_frame
                    
                    # Ensure health doesn't go below 0 (death is handled in update when health <= 0)
                    if self.health < 0:
                        self.health = 0
                    if animal.health < 0:
                        animal.health = 0
                    
                    # If one dies (health reached 0), the other gets a small health boost
                    # But don't set alive = False here - let the update method handle it
                    if self.health <= 0 and animal.health > 0:
                        animal.health = min(animal.max_health, animal.health + 10)
                    elif animal.health <= 0 and self.health > 0:
                        self.health = min(self.max_health, self.health + 10)
                    
                    # Track fight (will be tracked in Game.update)
                    self.fight_occurred = True
                    break  # Only fight one at a time
    
    def move(self, trees: List[Tree], animals: List['Animal'], dead_bodies: List[DeadBody], 
             walls: List['Wall'], seeds: List['Seed'], spatial_grid: 'SpatialGrid' = None,
             window_width: int = 1200, window_height: int = 800):
        # Check if in roaming mode (>50% health) or hunger mode (<50%)
        is_roaming_mode = (self.health / self.max_health) > 0.5
        
        # If health drops below 50%, immediately exit idle state
        if not is_roaming_mode and self.is_idle:
            self.is_idle = False
            self.idle_timer = 0
            self.idle_duration = 0
        
        # Handle idle/roaming behavior (only if health is above 50%)
        if is_roaming_mode:
            # Sometimes stay idle for a while
            if self.is_idle:
                self.idle_timer += 1
                if self.idle_timer >= self.idle_duration:
                    self.is_idle = False
                    self.idle_timer = 0
                    self.idle_duration = 0
            else:
                # Chance to start idling (only if health is above 50%)
                if random.random() < 0.01:  # 1% chance per frame
                    self.is_idle = True
                    self.idle_duration = random.randint(30, 120)  # Idle for 0.5-2 seconds
                    self.idle_timer = 0
            
            # If idle, don't move
            if self.is_idle:
                return
        
        # Check if herbivore is being chased by a predator
        self.being_chased = False
        if self.type == AnimalType.HERBIVORE:
            # Check for nearby predators
            if spatial_grid:
                nearby_predators = spatial_grid.get_nearby(self.x, self.y, self.view_range * 1.5)
                nearby_predators = [a for a in nearby_predators if 
                                   isinstance(a, Animal) and a.alive and 
                                   (a.type == AnimalType.CARNIVORE or a.type == AnimalType.ALPHA_PREDATOR)]
            else:
                nearby_predators = [a for a in animals if 
                                   a != self and a.alive and 
                                   (a.type == AnimalType.CARNIVORE or a.type == AnimalType.ALPHA_PREDATOR)]
            
            for predator in nearby_predators:
                dx = predator.x - self.x
                dy = predator.y - self.y
                dist_sq = dx*dx + dy*dy
                # Check if predator is moving towards herbivore (chasing)
                if dist_sq < (self.view_range * 1.5) ** 2:
                    # Check if predator is facing towards herbivore
                    pred_to_herb_angle = math.atan2(dy, dx)
                    angle_diff = abs(pred_to_herb_angle - predator.angle)
                    # Normalize angle difference
                    while angle_diff > math.pi:
                        angle_diff -= 2 * math.pi
                    angle_diff = abs(angle_diff)
                    if angle_diff < math.pi / 3 or angle_diff > 5 * math.pi / 3:  # Within 60 degrees
                        self.being_chased = True
                        break
        
        # Find target based on type (only if in hunger mode or actively seeking)
        target = None
        min_dist_sq = float('inf')
        view_range_sq = self.view_range * self.view_range  # Use squared distance to avoid sqrt
        
        # Only actively seek food if in hunger mode
        if not is_roaming_mode:
            if self.type == AnimalType.HERBIVORE:
                # If being chased, prioritize finding a tree to hide in
                if self.being_chased and not self.on_tree:
                    # Look for any nearby tree to hide in (extended range when chased)
                    if spatial_grid:
                        nearby_trees = [t for t in trees if t.alive and 
                                       (t.x - self.x)**2 + (t.y - self.y)**2 < (self.view_range * 2) ** 2]
                    else:
                        nearby_trees = [t for t in trees if t.alive]
                    
                    for tree in nearby_trees:
                        dx = tree.x - self.x
                        dy = tree.y - self.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target = tree
                else:
                    # Look for trees with fruits (optimized - only check nearby)
                    if spatial_grid:
                        nearby_trees = [t for t in trees if t.alive and t.fruit_count > 0 and 
                                       (t.x - self.x)**2 + (t.y - self.y)**2 < view_range_sq]
                    else:
                        nearby_trees = [t for t in trees if t.alive and t.fruit_count > 0]
                    
                    for tree in nearby_trees:
                        dx = tree.x - self.x
                        dy = tree.y - self.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target = tree
            
            elif self.type == AnimalType.TREE_EATER:
                # Look for trees (optimized)
                if spatial_grid:
                    nearby_trees = [t for t in trees if t.alive and 
                                   (t.x - self.x)**2 + (t.y - self.y)**2 < view_range_sq]
                else:
                    nearby_trees = [t for t in trees if t.alive]
                
                for tree in nearby_trees:
                    dx = tree.x - self.x
                    dy = tree.y - self.y
                    dist_sq = dx*dx + dy*dy
                    if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        target = tree
            
            elif self.type == AnimalType.CARNIVORE:
                # Hunt if health is below 50% (hunger mode)
                # Prefer non-decomposers unless health is below 30%
                health_ratio = self.health / self.max_health
                prefer_non_decomposers = health_ratio > 0.3  # Only eat decomposers if health < 30%
                
                # Use spatial grid for efficient neighbor queries
                if spatial_grid:
                    nearby_animals = spatial_grid.get_nearby(self.x, self.y, self.view_range)
                    nearby_animals = [a for a in nearby_animals if 
                                     isinstance(a, Animal) and a != self and a.alive and 
                                     a.type != AnimalType.CARNIVORE and a.type != AnimalType.ALPHA_PREDATOR]
                else:
                    nearby_animals = [a for a in animals if 
                                     a != self and a.alive and 
                                     a.type != AnimalType.CARNIVORE and a.type != AnimalType.ALPHA_PREDATOR]
                
                # Filter out herbivores that are hiding in trees (invisible to predators)
                visible_animals = []
                for a in nearby_animals:
                    if a.type == AnimalType.HERBIVORE:
                        # Check if herbivore is on a tree
                        is_on_tree = False
                        for tree in trees:
                            if tree.alive:
                                dx = a.x - tree.x
                                dy = a.y - tree.y
                                dist_sq = dx*dx + dy*dy
                                tree_crown_radius = tree.size / 2
                                if dist_sq < tree_crown_radius * tree_crown_radius:
                                    is_on_tree = True
                                    break
                        if not is_on_tree:  # Only add if not hiding in tree
                            visible_animals.append(a)
                    else:
                        visible_animals.append(a)
                
                # Separate decomposers from other prey
                preferred_prey = [a for a in visible_animals if a.type != AnimalType.DECOMPOSER]
                decomposer_prey = [a for a in visible_animals if a.type == AnimalType.DECOMPOSER]
                
                # Search preferred prey first, only consider decomposers if health < 30%
                search_list = preferred_prey if prefer_non_decomposers else (preferred_prey + decomposer_prey)
                
                for animal in search_list:
                    dx = animal.x - self.x
                    dy = animal.y - self.y
                    dist_sq = dx*dx + dy*dy
                    if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        target = animal
                
                # If no preferred prey found and health is low, consider decomposers
                if target is None and not prefer_non_decomposers:
                    for animal in decomposer_prey:
                        dx = animal.x - self.x
                        dy = animal.y - self.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target = animal
            
            elif self.type == AnimalType.ALPHA_PREDATOR:
                # Alpha predators hunt all other animals (optimized)
                # Prefer non-decomposers unless health is below 30%
                health_ratio = self.health / self.max_health
                prefer_non_decomposers = health_ratio > 0.3  # Only eat decomposers if health < 30%
                
                if spatial_grid:
                    nearby_animals = spatial_grid.get_nearby(self.x, self.y, self.view_range)
                    nearby_animals = [a for a in nearby_animals if 
                                     isinstance(a, Animal) and a != self and a.alive and 
                                     a.type != AnimalType.ALPHA_PREDATOR]
                else:
                    nearby_animals = [a for a in animals if 
                                     a != self and a.alive and a.type != AnimalType.ALPHA_PREDATOR]
                
                # Filter out herbivores that are hiding in trees (invisible to predators)
                visible_animals = []
                for a in nearby_animals:
                    if a.type == AnimalType.HERBIVORE:
                        # Check if herbivore is on a tree
                        is_on_tree = False
                        for tree in trees:
                            if tree.alive:
                                dx = a.x - tree.x
                                dy = a.y - tree.y
                                dist_sq = dx*dx + dy*dy
                                tree_crown_radius = tree.size / 2
                                if dist_sq < tree_crown_radius * tree_crown_radius:
                                    is_on_tree = True
                                    break
                        if not is_on_tree:  # Only add if not hiding in tree
                            visible_animals.append(a)
                    else:
                        visible_animals.append(a)
                
                # Separate decomposers from other prey
                preferred_prey = [a for a in visible_animals if a.type != AnimalType.DECOMPOSER]
                decomposer_prey = [a for a in visible_animals if a.type == AnimalType.DECOMPOSER]
                
                # Search preferred prey first, only consider decomposers if health < 30%
                search_list = preferred_prey if prefer_non_decomposers else (preferred_prey + decomposer_prey)
                
                for animal in search_list:
                    dx = animal.x - self.x
                    dy = animal.y - self.y
                    dist_sq = dx*dx + dy*dy
                    if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        target = animal
                
                # If no preferred prey found and health is low, consider decomposers
                if target is None and not prefer_non_decomposers:
                    for animal in decomposer_prey:
                        dx = animal.x - self.x
                        dy = animal.y - self.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < view_range_sq and dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target = animal
            
            elif self.type == AnimalType.DECOMPOSER:
                # Look for dead bodies and seeds using "sniff" range (much longer than view_range)
                sniff_range_sq = self.sniff_range * self.sniff_range  # Use sniff_range for detection
                if spatial_grid:
                    # Use sniff_range for initial detection
                    nearby_entities = spatial_grid.get_nearby(self.x, self.y, self.sniff_range)
                    nearby_bodies = [e for e in nearby_entities if isinstance(e, DeadBody) and e.alive]
                    nearby_seeds = [e for e in nearby_entities if isinstance(e, Seed) and e.alive]
                else:
                    nearby_bodies = [b for b in dead_bodies if b.alive]
                    nearby_seeds = [s for s in seeds if s.alive]
                
                # Check dead bodies first (using sniff_range)
                for body in nearby_bodies:
                    dx = body.x - self.x
                    dy = body.y - self.y
                    dist_sq = dx*dx + dy*dy
                    if dist_sq < sniff_range_sq and dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        target = body
                
                # Then check seeds if no body found (using sniff_range)
                if target is None:
                    for seed in nearby_seeds:
                        dx = seed.x - self.x
                        dy = seed.y - self.y
                        dist_sq = dx*dx + dy*dy
                        if dist_sq < sniff_range_sq and dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target = seed
        
        # Move towards target or wander
        if target:
            dx = target.x - self.x
            dy = target.y - self.y
            dist_sq = dx*dx + dy*dy
            if dist_sq > 0.01:  # Avoid division by zero
                self.angle = math.atan2(dy, dx)
        else:
            # Wander randomly
            self.angle += random.uniform(-0.3, 0.3)
        
        # Apply movement
        # Slow down in river or mud
        speed_multiplier = 1.0
        if self.in_river:
            speed_multiplier = 0.5  # Half speed in river
        elif self.in_mud:
            speed_multiplier = 0.6  # 60% speed in mud (slightly faster than river)
        move_speed = self.speed * speed_multiplier
        new_x = self.x + math.cos(self.angle) * move_speed
        new_y = self.y + math.sin(self.angle) * move_speed
        
        # Check wall collisions
        can_move = True
        for wall in walls:
            if wall.collides_with(new_x, new_y, self.size):
                can_move = False
                # Bounce off wall
                self.angle += math.pi + random.uniform(-0.5, 0.5)
                break
        
        # Trees no longer act as physical barriers - they're hideouts for herbivores
        # Check if herbivore is on a tree (for hiding from predators)
        self.on_tree = False
        if self.type == AnimalType.HERBIVORE:
            for tree in trees:
                if tree.alive:
                    dx = self.x - tree.x
                    dy = self.y - tree.y
                    dist_sq = dx*dx + dy*dy
                    tree_crown_radius = tree.size / 2  # Tree crown radius
                    if dist_sq < tree_crown_radius * tree_crown_radius:
                        self.on_tree = True
                        break
        
        if can_move:
            # Use passed window dimensions
            self.x = max(self.size, min(window_width - self.size, new_x))
            self.y = max(self.size, min(window_height - self.size, new_y))
    
    def try_eat(self, trees: List[Tree], animals: List['Animal'], dead_bodies: List[DeadBody], seeds: List['Seed'],
                spatial_grid: 'SpatialGrid' = None):
        if self.type == AnimalType.CARNIVORE:
            # Carnivores don't use hunger, only hunt when health < 80%
            health_ratio = self.health / self.max_health
            if health_ratio >= 0.8:  # 4/5 or more full, don't hunt
                return
        else:
            # Other animals use health system
            if self.health >= self.max_health:
                return
        
        if self.type == AnimalType.HERBIVORE:
            # Only check nearby trees
            nearby_trees = trees
            if spatial_grid:
                nearby_trees = [t for t in trees if t.alive and 
                               (t.x - self.x)**2 + (t.y - self.y)**2 < (self.size + t.size/2)**2]
            else:
                nearby_trees = [t for t in trees if t.alive]
            
            for tree in nearby_trees:
                dx = tree.x - self.x
                dy = tree.y - self.y
                dist_sq = dx*dx + dy*dy
                collision_dist = self.size + tree.size/2
                if dist_sq < collision_dist * collision_dist:
                    # Eat 1-3 berries (or until health is full)
                    # Each berry fills 1/5 health (20% = 20 health points)
                    berries_to_eat = random.randint(1, 3)
                    berries_eaten = 0
                    
                    for _ in range(berries_to_eat):
                        # Stop if health is full
                        if self.health >= self.max_health:
                            break
                        
                        # Try to eat a berry
                        if tree.remove_fruit():
                            # Each berry restores 1/5 health (20%)
                            berry_health = self.max_health / 5
                            self.health = min(self.max_health, self.health + berry_health)
                            berries_eaten += 1
                            
                            # 50% chance to get a seed (only if not at max capacity)
                            if random.random() < 0.5 and self.carried_seeds < self.max_carried_seeds:
                                self.carried_seeds += 1
                        else:
                            # No more fruits on this tree
                            break
                    
                    # If we ate at least one berry, we're done with this tree
                    if berries_eaten > 0:
                        break
        
        elif self.type == AnimalType.TREE_EATER:
            for tree in trees:
                if tree.alive and self.distance_to(tree) < self.size + tree.size/2:
                    was_alive = tree.alive
                    tree.take_damage(0.5)
                    self.health = min(self.max_health, self.health + 0.3)
                    # Track if tree died from being eaten (will be tracked in Game.update)
                    if not tree.alive and was_alive:
                        tree.death_reason = "eaten"
                        # 30% chance to carry a seed when eating a tree
                        if random.random() < 0.3 and self.carried_seeds < self.max_carried_seeds:
                            self.carried_seeds += 1
                    # Poop periodically when eating (not every frame to prevent flickering)
                    if not hasattr(self, 'poop_timer'):
                        self.poop_timer = 0
                    self.poop_timer += 1
                    if self.poop_timer >= 60:  # Poop every 60 frames (1 second at 60fps)
                        # Add small random offset to prevent seeds from stacking exactly on top of each other
                        seed = Seed(self.x + random.uniform(-3, 3), self.y + random.uniform(-3, 3), 
                                   from_fruit=False, is_big_poop=False)
                        seeds.append(seed)
                        seed.tracked_creation = True
                        seed.tracked_dispersed = True
                        self.poop_timer = 0
                    break
            else:
                # Not eating a tree - reset poop timer
                if hasattr(self, 'poop_timer'):
                    self.poop_timer = 0
        
        elif self.type == AnimalType.CARNIVORE:
            # Hunt non-predator animals (optimized)
            # Prefer non-decomposers unless health is below 50%
            health_ratio = self.health / self.max_health
            prefer_non_decomposers = health_ratio > 0.5  # Only eat decomposers if health < 50%
            
            if spatial_grid:
                nearby_animals = spatial_grid.get_nearby(self.x, self.y, self.size + 20)
                nearby_animals = [a for a in nearby_animals if 
                                 isinstance(a, Animal) and a != self and a.alive and 
                                 a.type != AnimalType.CARNIVORE and a.type != AnimalType.ALPHA_PREDATOR]
            else:
                nearby_animals = [a for a in animals if 
                                 a != self and a.alive and 
                                 a.type != AnimalType.CARNIVORE and a.type != AnimalType.ALPHA_PREDATOR]
            
            # Separate decomposers from other prey
            preferred_prey = [a for a in nearby_animals if a.type != AnimalType.DECOMPOSER]
            decomposer_prey = [a for a in nearby_animals if a.type == AnimalType.DECOMPOSER]
            
            # Track which prey are currently in collision radius (where kill attempts can happen)
            current_prey_in_radius = set()
            
            # Try preferred prey first
            for animal in preferred_prey:
                dx = animal.x - self.x
                dy = animal.y - self.y
                dist_sq = dx*dx + dy*dy
                collision_dist = self.size + animal.size
                collision_dist_sq = collision_dist * collision_dist
                
                # Check if in collision distance (can attempt kill)
                if dist_sq < collision_dist_sq:
                    current_prey_in_radius.add(id(animal))
                    
                    # Check if we've already attempted on this prey
                    if id(animal) not in self.attempted_kills:
                        # Roll 1 in 3 chance (33%)
                        if random.random() < 1/3:
                            # Success! Kill the prey
                            animal.alive = False
                            # Eating preferred prey restores 20% health (100% / 5 = 20%)
                            self.health = min(self.max_health, self.health + (self.max_health / 5))
                            # Carnivores poop when they eat
                            seed = Seed(self.x, self.y, from_fruit=False, is_big_poop=False)
                            seeds.append(seed)
                            seed.tracked_creation = True
                            seed.tracked_dispersed = True
                            # Remove from attempted_kills since we succeeded
                            if id(animal) in self.attempted_kills:
                                del self.attempted_kills[id(animal)]
                            break
                        else:
                            # Failed attempt - mark it
                            self.attempted_kills[id(animal)] = True
            
            # Only eat decomposers if health is low and no preferred prey found
            if not prefer_non_decomposers:
                # Health is below 30%, can eat decomposers
                # Only eat animals that are alive and have health > 0 (safety check)
                for animal in decomposer_prey:
                    if not animal.alive or animal.health <= 0:
                        continue
                    dx = animal.x - self.x
                    dy = animal.y - self.y
                    dist_sq = dx*dx + dy*dy
                    collision_dist = self.size + animal.size
                    collision_dist_sq = collision_dist * collision_dist
                    
                    # Check if in collision distance (can attempt kill)
                    if dist_sq < collision_dist_sq:
                        current_prey_in_radius.add(id(animal))
                        
                        # Check if we've already attempted on this prey
                        if id(animal) not in self.attempted_kills:
                            # Roll 1 in 3 chance (33%)
                            if random.random() < 1/3:
                                # Success! Kill the prey
                                animal.alive = False
                                # Eating decomposers only restores 10% health
                                if animal.type == AnimalType.DECOMPOSER:
                                    self.health = min(self.max_health, self.health + (self.max_health / 10))
                                else:
                                    # Eating preferred prey restores 20% health (100% / 5 = 20%)
                                    self.health = min(self.max_health, self.health + (self.max_health / 5))
                                # Carnivores poop when they eat
                                # Add small random offset to prevent seeds from stacking exactly on top of each other
                                seed = Seed(self.x + random.uniform(-3, 3), self.y + random.uniform(-3, 3), 
                                           from_fruit=False, is_big_poop=False)
                                seeds.append(seed)
                                seed.tracked_creation = True
                                seed.tracked_dispersed = True
                                # Remove from attempted_kills since we succeeded
                                if id(animal) in self.attempted_kills:
                                    del self.attempted_kills[id(animal)]
                                break
                            else:
                                # Failed attempt - mark it
                                self.attempted_kills[id(animal)] = True
            
            # Reset attempts for prey that left the radius
            self.attempted_kills = {prey_id: attempted for prey_id, attempted in self.attempted_kills.items() 
                                   if prey_id in current_prey_in_radius}
        
        elif self.type == AnimalType.DECOMPOSER:
            # Can eat dead bodies and seeds (optimized)
            if spatial_grid:
                nearby_entities = spatial_grid.get_nearby(self.x, self.y, self.size + 20)
                nearby_bodies = [e for e in nearby_entities if isinstance(e, DeadBody) and e.alive]
                nearby_seeds = [e for e in nearby_entities if isinstance(e, Seed) and e.alive]
            else:
                nearby_bodies = [b for b in dead_bodies if b.alive]
                nearby_seeds = [s for s in seeds if s.alive]
            
            # Check dead bodies first
            for body in nearby_bodies:
                dx = body.x - self.x
                dy = body.y - self.y
                dist_sq = dx*dx + dy*dy
                collision_dist = self.size + body.size
                if dist_sq < collision_dist * collision_dist:
                    if not body.being_decomposed:
                        body.being_decomposed = True
                        body.decay_time = 300  # Reset decay timer when decomposer starts
                    body.decay_time -= 10  # Accelerate decay
                    self.health = min(self.max_health, self.health + 20)
                    if body.decay_time <= 0:
                        body.alive = False
                    break
            
            # Can also eat seeds/poop
            if self.health < self.max_health:
                for seed in nearby_seeds:
                    dx = seed.x - self.x
                    dy = seed.y - self.y
                    dist_sq = dx*dx + dy*dy
                    collision_dist = self.size + seed.size
                    if dist_sq < collision_dist * collision_dist:
                        # Big poop requires 2 decomposers
                        if hasattr(seed, 'is_big_poop') and seed.is_big_poop:
                            # Track which decomposers are working on this big poop
                            if not hasattr(seed, 'decomposers_working'):
                                seed.decomposers_working = set()
                            # Add this decomposer to the set
                            seed.decomposers_working.add(id(self))
                            # Only consume if 2 or more unique decomposers are working on it
                            if len(seed.decomposers_working) >= 2:
                                seed.alive = False
                                self.health = min(self.max_health, self.health + 30)  # Big poop gives more health
                            else:
                                # Still get some health for working on it
                                self.health = min(self.max_health, self.health + 5)
                        else:
                            # Regular seed/poop - can eat alone
                            seed.alive = False
                            self.health = min(self.max_health, self.health + 15)
                        break
        
        elif self.type == AnimalType.ALPHA_PREDATOR:
            # Alpha predators eat all other animals (except other alpha predators - they fight instead)
            # Prefer non-decomposers unless health is below 30%
            health_ratio = self.health / self.max_health
            prefer_non_decomposers = health_ratio > 0.3  # Only eat decomposers if health < 30%
            
            # Separate decomposers from other prey
            preferred_prey = [a for a in animals if 
                            a != self and a.alive and 
                            a.type != AnimalType.ALPHA_PREDATOR and
                            a.type != AnimalType.DECOMPOSER]
            decomposer_prey = [a for a in animals if 
                             a != self and a.alive and 
                             a.type == AnimalType.DECOMPOSER]
            
            # Track which prey are currently in collision radius (where kill attempts can happen)
            current_prey_in_radius = set()
            
            # Try preferred prey first
            # Only eat animals that are alive and have health > 0 (safety check)
            for animal in preferred_prey:
                if not animal.alive or animal.health <= 0:
                    continue
                dist = self.distance_to(animal)
                collision_dist = self.size + animal.size
                
                # Check if in collision distance (can attempt kill)
                if dist < collision_dist:
                    current_prey_in_radius.add(id(animal))
                    
                    # Check if we've already attempted on this prey
                    if id(animal) not in self.attempted_kills:
                        # Roll 1 in 2 chance (50%)
                        if random.random() < 1/2:
                            # Success! Kill the prey
                            animal.alive = False
                            # Eating restores health
                            self.health = min(self.max_health, self.health + (self.max_health / 3))
                            # Alpha predators create big poop (requires 2 decomposers)
                            # Add small random offset to prevent seeds from stacking exactly on top of each other
                            seed = Seed(self.x + random.uniform(-3, 3), self.y + random.uniform(-3, 3), 
                                       from_fruit=False, is_big_poop=True)
                            seeds.append(seed)
                            seed.tracked_creation = True
                            seed.tracked_dispersed = True
                            # Remove from attempted_kills since we succeeded
                            if id(animal) in self.attempted_kills:
                                del self.attempted_kills[id(animal)]
                            break
                        else:
                            # Failed attempt - mark it
                            self.attempted_kills[id(animal)] = True
            
            # Only eat decomposers if health is low and no preferred prey found
            if not prefer_non_decomposers:
                # Health is below 30%, can eat decomposers
                # Only eat animals that are alive and have health > 0 (safety check)
                for animal in decomposer_prey:
                    if not animal.alive or animal.health <= 0:
                        continue
                    dist = self.distance_to(animal)
                    collision_dist = self.size + animal.size
                    
                    # Check if in collision distance (can attempt kill)
                    if dist < collision_dist:
                        current_prey_in_radius.add(id(animal))
                        
                        # Check if we've already attempted on this prey
                        if id(animal) not in self.attempted_kills:
                            # Roll 1 in 2 chance (50%)
                            if random.random() < 1/2:
                                # Success! Kill the prey
                                animal.alive = False
                                # Eating decomposers only restores 10% health
                                if animal.type == AnimalType.DECOMPOSER:
                                    self.health = min(self.max_health, self.health + (self.max_health / 10))
                                else:
                                    # Eating preferred prey restores 33% health
                                    self.health = min(self.max_health, self.health + (self.max_health / 3))
                                # Remove from attempted_kills since we succeeded
                                if id(animal) in self.attempted_kills:
                                    del self.attempted_kills[id(animal)]
                                break
                            else:
                                # Failed attempt - mark it
                                self.attempted_kills[id(animal)] = True
            
            # Reset attempts for prey that left the radius
            self.attempted_kills = {prey_id: attempted for prey_id, attempted in self.attempted_kills.items() 
                                   if prey_id in current_prey_in_radius}
    
    def try_start_mating(self, animals: List['Animal'], spatial_grid: 'SpatialGrid' = None):
        """Try to find a mate and start mating"""
        if self.mating:
            return
        
        # Find nearby mate of same type
        if spatial_grid:
            nearby_animals = spatial_grid.get_nearby(self.x, self.y, self.mating_radius)
            nearby_animals = [a for a in nearby_animals if 
                            isinstance(a, Animal) and a != self and a.alive and 
                            a.type == self.type and not a.mating]
        else:
            nearby_animals = [a for a in animals if 
                            a != self and a.alive and a.type == self.type and not a.mating]
        
        for animal in nearby_animals:
            dist_sq = (animal.x - self.x)**2 + (animal.y - self.y)**2
            if dist_sq < self.mating_radius * self.mating_radius:
                # Check if mate is healthy enough (lowered thresholds)
                mate_healthy = False
                # All animals use health for mating (50% threshold)
                mate_healthy = animal.health > animal.max_health * 0.5
                
                if mate_healthy:
                    # Check if there are only 2 animals of this species in their combined radius
                    # Calculate the center point between the two animals
                    center_x = (self.x + animal.x) / 2
                    center_y = (self.y + animal.y) / 2
                    
                    # Calculate the distance between the two animals
                    dist = math.sqrt(dist_sq)
                    
                    # Combined radius = distance between them + mating_radius on each side
                    combined_radius = dist + self.mating_radius
                    combined_radius_sq = combined_radius * combined_radius
                    
                    # Count how many animals of the same type are within the combined radius
                    same_species_count = 0
                    if spatial_grid:
                        # Use spatial grid for efficient query
                        nearby_all = spatial_grid.get_nearby(center_x, center_y, combined_radius)
                        same_species_count = sum(1 for a in nearby_all 
                                                if isinstance(a, Animal) and a.alive and 
                                                a.type == self.type)
                    else:
                        # Fallback: check all animals
                        for a in animals:
                            if a.alive and a.type == self.type:
                                dx = a.x - center_x
                                dy = a.y - center_y
                                if dx*dx + dy*dy <= combined_radius_sq:
                                    same_species_count += 1
                    
                    # Only allow mating if there are exactly 2 animals of this species in the combined radius
                    if same_species_count == 2:
                        # Chance to start mating (increased from 30% to 50% per frame when close)
                        if random.random() < 0.5:
                            # Start mating
                            self.mating = True
                            self.mating_timer = 0
                            self.mating_partner = animal
                            animal.mating = True
                            animal.mating_timer = 0
                            animal.mating_partner = self
                            # Track mating attempt (will be tracked in Game.update)
                            self.mating_started = True
                            break
    
    def draw(self, screen: pygame.Surface):
        if not self.alive:
            return
        
        # Hibernation disabled - always draw carnivores
        
        # Draw body
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        
        # Draw heart above mating animals
        if self.mating:
            heart_y = self.y - self.size - 15
            # Draw a simple heart shape (two circles and a triangle)
            heart_size = 6
            # Left circle
            pygame.draw.circle(screen, (255, 0, 0), 
                             (int(self.x - heart_size/2), int(heart_y - heart_size/2)), heart_size)
            # Right circle
            pygame.draw.circle(screen, (255, 0, 0), 
                             (int(self.x + heart_size/2), int(heart_y - heart_size/2)), heart_size)
            # Triangle (pointing down)
            heart_points = [
                (int(self.x), int(heart_y + heart_size)),
                (int(self.x - heart_size), int(heart_y)),
                (int(self.x + heart_size), int(heart_y))
            ]
            pygame.draw.polygon(screen, (255, 0, 0), heart_points)
        
        # Draw two small black eyes on the front of the animal
        # Position eyes on either side of the direction the animal is facing
        eye_offset = self.size * 0.3  # Distance from center
        eye_size = max(2, int(self.size * 0.2))  # Small black dots
        perp_angle = self.angle + math.pi / 2  # Perpendicular to direction
        
        # Left eye
        left_eye_x = self.x + math.cos(self.angle) * (self.size * 0.5) + math.cos(perp_angle) * eye_offset
        left_eye_y = self.y + math.sin(self.angle) * (self.size * 0.5) + math.sin(perp_angle) * eye_offset
        pygame.draw.circle(screen, BLACK, (int(left_eye_x), int(left_eye_y)), eye_size)
        
        # Right eye
        right_eye_x = self.x + math.cos(self.angle) * (self.size * 0.5) - math.cos(perp_angle) * eye_offset
        right_eye_y = self.y + math.sin(self.angle) * (self.size * 0.5) - math.sin(perp_angle) * eye_offset
        pygame.draw.circle(screen, BLACK, (int(right_eye_x), int(right_eye_y)), eye_size)
        
        # Draw health bar
        bar_width = self.size * 2
        bar_height = 3
        health_ratio = self.health / self.max_health
        pygame.draw.rect(screen, RED, 
                        (int(self.x - bar_width/2), int(self.y - self.size - 6), 
                         bar_width, bar_height))
        pygame.draw.rect(screen, GREEN, 
                        (int(self.x - bar_width/2), int(self.y - self.size - 6), 
                         int(bar_width * health_ratio), bar_height))

class RiverSegment:
    def __init__(self, x1: float, y1: float, x2: float, y2: float, width: float):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.width = width
        
        # Calculate flow direction
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            self.flow_x = dx / length
            self.flow_y = dy / length
        else:
            self.flow_x = 0
            self.flow_y = 0
    
    def contains_point(self, x: float, y: float) -> bool:
        # Check if point is within the river segment
        # Project point onto line segment
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        length_sq = dx*dx + dy*dy
        
        if length_sq == 0:
            return False
        
        t = max(0, min(1, ((x - self.x1) * dx + (y - self.y1) * dy) / length_sq))
        proj_x = self.x1 + t * dx
        proj_y = self.y1 + t * dy
        
        dist = math.sqrt((x - proj_x)**2 + (y - proj_y)**2)
        return dist < self.width / 2
    
    def draw(self, screen: pygame.Surface):
        # Draw river as a thick line
        pygame.draw.line(screen, BLUE, (int(self.x1), int(self.y1)), 
                        (int(self.x2), int(self.y2)), int(self.width))
        # Draw flow direction indicator
        mid_x = (self.x1 + self.x2) / 2
        mid_y = (self.y1 + self.y2) / 2
        arrow_x = mid_x + self.flow_x * 20
        arrow_y = mid_y + self.flow_y * 20
        pygame.draw.line(screen, CYAN, (int(mid_x), int(mid_y)), 
                        (int(arrow_x), int(arrow_y)), 3)

class Cave(Entity):
    """Safe caves where herbivores can hide from predators"""
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.radius = 25
        self.entrance_radius = 30  # Slightly larger for easier entry
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside the cave"""
        dist = math.sqrt((x - self.x)**2 + (y - self.y)**2)
        return dist < self.radius
    
    def is_near_entrance(self, x: float, y: float) -> bool:
        """Check if a point is near the cave entrance"""
        dist = math.sqrt((x - self.x)**2 + (y - self.y)**2)
        return dist < self.entrance_radius
    
    def draw(self, screen: pygame.Surface):
        # Draw cave as a dark circle with entrance
        pygame.draw.circle(screen, (40, 40, 40), (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (60, 60, 60), (int(self.x), int(self.y)), self.radius, 2)
        # Draw entrance indicator
        pygame.draw.circle(screen, (80, 80, 80), (int(self.x), int(self.y)), 5)

class MudPuddle(Entity):
    """Mud puddles that slow down animals"""
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.radius = random.uniform(30, 60)  # Variable size puddles
        self.size = self.radius  # For compatibility with Entity
        # Create irregular blob shape using multiple points
        self.blob_points = []
        num_points = 12  # Number of points for irregular shape
        for i in range(num_points):
            angle = (2 * math.pi * i) / num_points
            # Vary radius to create irregular shape
            r = self.radius * (0.7 + random.uniform(0, 0.6))
            px = self.x + math.cos(angle) * r
            py = self.y + math.sin(angle) * r
            self.blob_points.append((px, py))
        
        # No texture shapes needed - monotone brown
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside the mud puddle"""
        dist = math.sqrt((x - self.x)**2 + (y - self.y)**2)
        return dist < self.radius
    
    def overlaps_river(self, river_segments: List['RiverSegment']) -> bool:
        """Check if mud puddle overlaps with any river segment"""
        for segment in river_segments:
            # Check if center of puddle is in river
            if segment.contains_point(self.x, self.y):
                return True
            # Check if any point on the puddle's edge is in river
            # Sample points around the puddle's perimeter
            for i in range(8):
                angle = (2 * math.pi * i) / 8
                check_x = self.x + math.cos(angle) * self.radius
                check_y = self.y + math.sin(angle) * self.radius
                if segment.contains_point(check_x, check_y):
                    return True
        return False
    
    def draw(self, screen: pygame.Surface):
        # Draw mud puddle as irregular organic blob shape
        MUD_COLOR = (139, 121, 94)  # Light brown color
        DARK_MUD = (100, 85, 65)  # Darker brown for border
        
        # Convert blob points to integer coordinates
        int_points = [(int(p[0]), int(p[1])) for p in self.blob_points]
        
        # Draw filled irregular polygon
        if len(int_points) >= 3:
            pygame.draw.polygon(screen, MUD_COLOR, int_points)
            # Draw darker border
            pygame.draw.polygon(screen, DARK_MUD, int_points, 2)
        
        # No texture shapes - just monotone brown

class Wall:
    def __init__(self, x1: float, y1: float, x2: float, y2: float):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.width = 5
    
    def collides_with(self, x: float, y: float, radius: float) -> bool:
        # Check if circle collides with line segment
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        length_sq = dx*dx + dy*dy
        
        if length_sq == 0:
            return False
        
        t = max(0, min(1, ((x - self.x1) * dx + (y - self.y1) * dy) / length_sq))
        proj_x = self.x1 + t * dx
        proj_y = self.y1 + t * dy
        
        dist = math.sqrt((x - proj_x)**2 + (y - proj_y)**2)
        return dist < radius + self.width/2
    
    def draw(self, screen: pygame.Surface):
        pygame.draw.line(screen, DARK_GRAY, (int(self.x1), int(self.y1)), 
                        (int(self.x2), int(self.y2)), self.width)

class SpatialGrid:
    """Simple spatial grid for efficient neighbor queries"""
    def __init__(self, cell_size: int = 100):
        self.cell_size = cell_size
        self.grid: dict = {}
    
    def _get_key(self, x: float, y: float) -> tuple:
        return (int(x // self.cell_size), int(y // self.cell_size))
    
    def clear(self):
        self.grid.clear()
    
    def add(self, entity: Entity):
        key = self._get_key(entity.x, entity.y)
        if key not in self.grid:
            self.grid[key] = []
        self.grid[key].append(entity)
    
    def get_nearby(self, x: float, y: float, radius: float) -> List[Entity]:
        """Get entities within radius"""
        nearby = []
        # Check current cell and adjacent cells
        center_key = self._get_key(x, y)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (center_key[0] + dx, center_key[1] + dy)
                if key in self.grid:
                    for entity in self.grid[key]:
                        if entity.alive:
                            dist_sq = (entity.x - x)**2 + (entity.y - y)**2
                            if dist_sq <= radius * radius:
                                nearby.append(entity)
        return nearby

class Game:
    def __init__(self):
        # Force NVIDIA GPU usage on Windows (if available)
        import os
        # Set environment variable to prefer NVIDIA GPU
        os.environ['SDL_VIDEODRIVER'] = 'windib'  # Windows DirectX backend
        # Try to set NVIDIA GPU as preferred (Windows)
        try:
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first CUDA device
        except:
            pass
        
        # Enable hardware acceleration if available
        pygame.display.init()
        
        # Make window resizable
        self.window_width = INITIAL_WINDOW_WIDTH
        self.window_height = INITIAL_WINDOW_HEIGHT
        
        # Try to use maximum hardware acceleration flags for NVIDIA RTX
        # HWSURFACE = Hardware surface (GPU accelerated)
        # DOUBLEBUF = Double buffering (smooth rendering)
        # RESIZABLE = Allow window resizing
        # SCALED = Use GPU scaling (better performance)
        try:
            flags = pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE
            # Try to add SCALED flag if available (pygame 2.0+)
            if hasattr(pygame, 'SCALED'):
                flags |= pygame.SCALED
            self.screen = pygame.display.set_mode((self.window_width, self.window_height), flags)
            print("[OK] Using hardware-accelerated rendering (GPU)")
        except Exception as e:
            # Fallback if hardware acceleration not available
            print(f"[WARNING] Hardware acceleration not available: {e}")
            self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        
        # Enable vsync for smoother rendering (uses GPU)
        try:
            pygame.display.set_mode((self.window_width, self.window_height), 
                                   pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE)
        except:
            pass
        
        pygame.display.set_caption("Ecological Simulation (GPU Accelerated)")
        
        # Store original dimensions for scaling
        self.original_width = INITIAL_WINDOW_WIDTH
        self.original_height = INITIAL_WINDOW_HEIGHT
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Simple font system
        self.font = pygame.font.Font(None, 24)  # Standard font
        self.font_small = pygame.font.Font(None, 20)  # Smaller font for hints
        
        # Rendering optimizations
        self.use_dirty_rects = False  # Disable for now - can cause issues with full screen updates
        self.dirty_rects = []
        
        # Performance optimization flags
        self.frame_skip_counter = 0
        self.update_batch_size = 10  # Process entities in batches
        
        # Surface caching for better GPU utilization
        self.cached_surfaces = {}
        self.cache_enabled = True
        
        # Batch rendering lists
        self.batch_circles = []  # List of (color, pos, radius) tuples
        self.batch_lines = []    # List of (color, start, end, width) tuples
        
        # Game entities
        self.trees: List[Tree] = []
        self.animals: List[Animal] = []
        self.dead_bodies: List[DeadBody] = []
        self.seeds: List[Seed] = []
        self.caves: List[Cave] = []  # Caves for herbivores and hibernating carnivores
        self.mud_puddles: List[MudPuddle] = []  # Mud puddles that slow movement
        self.river_segments: List[RiverSegment] = []
        self.walls: List[Wall] = []
        
        # Spatial grid for optimization
        self.spatial_grid = SpatialGrid(cell_size=100)
        
        # Alpha predator spawning
        self.alpha_spawn_timer = 0
        self.alpha_spawn_interval = 1800  # Spawn every 30 seconds at 60 FPS
        
        # Statistics tracking
        self.stats = {
            'trees_planted': 30,  # Initial trees
            'trees_died_age': 0,
            'trees_died_fertilization': 0,
            'trees_died_eaten': 0,
            'herbivores_born': 30,  # Initial herbivores
            'herbivores_died': 0,
            'carnivores_born': 12,  # 2x more (was 6)
            'carnivores_died': 0,
            'decomposers_born': 10,
            'decomposers_died': 0,
            'tree_eaters_born': 32,  # Increased spawn count
            'tree_eaters_died': 0,
            'seeds_created': 0,
            'seeds_fertilized': 0,
            'seeds_eaten': 0,
            'seeds_dispersed': 0,
            'seeds_grown_trees': 0,
            'mating_attempts': 0,
            'mating_successful': 0,
            'offspring_born': 0,
            'predator_fights': 0,
            'hibernation_entries': 0,
            'hibernation_exits': 0,
            'alpha_predators_spawned': 2,  # 2 alpha predators spawned at beginning
        }
        
        # Population history for graph (stores percentages over time)
        self.population_history: List[dict] = []  # List of {herbivore%, tree_eater%, carnivore%, decomposer%, alpha%}
        self.max_history_length = 10000  # Keep last 10000 data points (effectively unlimited)
        self.population_update_interval = 10  # Update every 10 frames
        self.population_update_counter = 0
        
        # Graph resizing
        self.graph_width = 300  # Current graph width (adjustable)
        self.graph_min_width = self.window_width // 2  # Minimum width (half screen)
        self.graph_max_width = self.window_width - 20  # Maximum width (almost full screen)
        self.graph_resizing = False  # Whether user is currently resizing
        self.graph_resize_anchor_x = 0  # X position of graph's right edge when resize started
        self.graph_resize_mouse_start_x = 0  # Mouse X position when resize started
        
        # Collapsible stats panel
        self.stats_panel_open = False
        self.stats_panel_rect = pygame.Rect(self.window_width - 250, 10, 240, 30)
        self.stats_panel_expanded_height = 400
        
        # User interaction
        self.selected_tool = "pointer"  # pointer, tree, herbivore, tree_eater, carnivore, decomposer, wall
        self.wall_start = None
        self.selected_entity = None  # Entity selected with pointer tool
        
        # Speed control
        self.speed_multiplier = 1
        self.speed_options = [1, 2, 5, 10, 50, 100]
        self.frame_skip = 0  # For rendering optimization
        self.update_counter = 0
        
        # Dropdown menu
        self.dropdown_open = False
        self.dropdown_options = [
            ("Pointer", "pointer", None),
            ("Tree", "tree", None),
            ("Herbivore", "herbivore", GREEN),
            ("Tree Eater", "tree_eater", ORANGE),
            ("Carnivore", "carnivore", RED),
            ("Decomposer", "decomposer", PURPLE),
            ("Alpha Predator", "alpha_predator", (139, 0, 0)),
            ("Wall", "wall", None)
        ]
        self.dropdown_rect = pygame.Rect(200, 10, 150, 25)
        self.dropdown_item_height = 25
        self.mouse_held = False
        self.mouse_hold_timer = 0
        
        # Create initial river
        self.create_river()
        
        # Create some initial entities
        self.initialize_ecosystem()
        
        # Initialize RTX detection variables
        self.rtx_active = False
        self.rtx_gpu_usage = 0.0  # GPU usage percentage
        self.rtx_check_counter = 0
        
        # Detect NVIDIA RTX GPU and get usage
        self.rtx_active, self.rtx_gpu_usage = self.detect_nvidia_rtx()
    
    def detect_nvidia_rtx(self) -> tuple[bool, float]:
        """Detect if NVIDIA RTX GPU is being used and return (is_active, gpu_usage_percent)"""
        import subprocess
        import platform
        
        gpu_usage = 0.0
        has_rtx = False
        
        # Check if we're on Windows
        if platform.system() != "Windows":
            # On non-Windows, check pygame renderer
            try:
                renderer = pygame.display.get_driver()
                if 'nvidia' in renderer.lower() or 'opengl' in renderer.lower():
                    has_rtx = True
            except:
                pass
            return (has_rtx, gpu_usage)
        
        # On Windows, check for NVIDIA GPU and usage
        try:
            # Method 1: Try nvidia-smi (most reliable) - get both name and utilization
            try:
                # Get GPU name
                name_result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                                           capture_output=True, text=True, timeout=2)
                if name_result.returncode == 0 and ('RTX' in name_result.stdout.upper() or 'nvidia' in name_result.stdout.lower()):
                    has_rtx = True
                    
                    # Get GPU utilization percentage
                    usage_result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                                                 capture_output=True, text=True, timeout=2)
                    if usage_result.returncode == 0:
                        try:
                            gpu_usage = float(usage_result.stdout.strip())
                        except:
                            gpu_usage = 0.0
            except:
                pass
            
            # Method 2: Check pygame renderer info (fallback)
            if not has_rtx:
                try:
                    renderer_info = pygame.display.Info()
                    renderer = pygame.display.get_driver()
                    # Check if hardware accelerated and using DirectX/OpenGL
                    if hasattr(renderer_info, 'hw') and renderer_info.hw:
                        if 'direct' in renderer.lower() or 'opengl' in renderer.lower():
                            # If hardware accelerated, likely using dedicated GPU
                            # Try one more check with nvidia-smi
                            try:
                                result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                                                      capture_output=True, text=True, timeout=1)
                                if 'RTX' in result.stdout.upper():
                                    has_rtx = True
                                    # Try to get usage
                                    usage_result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                                                                 capture_output=True, text=True, timeout=1)
                                    if usage_result.returncode == 0:
                                        try:
                                            gpu_usage = float(usage_result.stdout.strip())
                                        except:
                                            gpu_usage = 0.0
                            except:
                                # If nvidia-smi fails but we have hardware acceleration, assume GPU
                                has_rtx = True
                except:
                    pass
                
        except Exception as e:
            print(f"GPU detection error: {e}")
        
        return (has_rtx, gpu_usage)
    
    def create_river(self):
        # Create a winding river
        points = []
        x = 100
        y = self.window_height // 2
        
        for _ in range(15):
            points.append((x, y))
            x += random.uniform(60, 100)
            y += random.uniform(-80, 80)
            y = max(100, min(self.window_height - 100, y))
        
        # Create segments
        for i in range(len(points) - 1):
            segment = RiverSegment(points[i][0], points[i][1], 
                                  points[i+1][0], points[i+1][1], 40)
            self.river_segments.append(segment)
    
    def scale_entities(self, scale_x: float, scale_y: float):
        """Scale all entity positions when window is resized"""
        # Scale trees
        for tree in self.trees:
            tree.x *= scale_x
            tree.y *= scale_y
            # Clamp to new boundaries
            tree.x = max(tree.size/2, min(self.window_width - tree.size/2, tree.x))
            tree.y = max(tree.size/2, min(self.window_height - tree.size/2, tree.y))
        
        # Scale animals
        for animal in self.animals:
            animal.x *= scale_x
            animal.y *= scale_y
            # Clamp to new boundaries
            animal.x = max(animal.size, min(self.window_width - animal.size, animal.x))
            animal.y = max(animal.size, min(self.window_height - animal.size, animal.y))
        
        # Scale dead bodies
        for body in self.dead_bodies:
            body.x *= scale_x
            body.y *= scale_y
            body.x = max(body.size, min(self.window_width - body.size, body.x))
            body.y = max(body.size, min(self.window_height - body.size, body.y))
        
        # Scale seeds
        for seed in self.seeds:
            seed.x *= scale_x
            seed.y *= scale_y
            seed.x = max(seed.size, min(self.window_width - seed.size, seed.x))
            seed.y = max(seed.size, min(self.window_height - seed.size, seed.y))
        
        # Scale mud puddles
        for puddle in self.mud_puddles:
            old_x, old_y = puddle.x, puddle.y
            puddle.x *= scale_x
            puddle.y *= scale_y
            puddle.x = max(puddle.radius, min(self.window_width - puddle.radius, puddle.x))
            puddle.y = max(puddle.radius, min(self.window_height - puddle.radius, puddle.y))
            # Update blob points - scale relative to new center
            new_blob_points = []
            for px, py in puddle.blob_points:
                # Calculate offset from old center
                offset_x = px - old_x
                offset_y = py - old_y
                # Scale offset and add to new center
                new_blob_points.append((puddle.x + offset_x * scale_x, 
                                       puddle.y + offset_y * scale_y))
            puddle.blob_points = new_blob_points
        
        # Scale caves
        for cave in self.caves:
            cave.x *= scale_x
            cave.y *= scale_y
            cave.x = max(cave.radius, min(self.window_width - cave.radius, cave.x))
            cave.y = max(cave.radius, min(self.window_height - cave.radius, cave.y))
        
        # Scale river segments
        for segment in self.river_segments:
            segment.x1 *= scale_x
            segment.y1 *= scale_y
            segment.x2 *= scale_x
            segment.y2 *= scale_y
            # Recalculate flow direction
            dx = segment.x2 - segment.x1
            dy = segment.y2 - segment.y1
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                segment.flow_x = dx / length
                segment.flow_y = dy / length
            else:
                segment.flow_x = 0
                segment.flow_y = 0
        
        # Scale walls
        for wall in self.walls:
            wall.x1 *= scale_x
            wall.y1 *= scale_y
            wall.x2 *= scale_x
            wall.y2 *= scale_y
    
    def initialize_ecosystem(self):
        # Add trees (with overlap checking - trees act as natural barriers)
        trees_placed = 0
        attempts = 0
        max_attempts = 2000  # Prevent infinite loop (increased for more trees)
        while trees_placed < 60 and attempts < max_attempts:  # Doubled from 30 to 60
            attempts += 1
            new_tree = Tree(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50)
            )
            # Check for overlap with existing trees
            can_place = True
            for existing_tree in self.trees:
                if existing_tree.alive:
                    dist = math.sqrt((new_tree.x - existing_tree.x)**2 + 
                                   (new_tree.y - existing_tree.y)**2)
                    if dist < (new_tree.size + existing_tree.size) / 2:
                        can_place = False
                        break
            
            if can_place:
                self.trees.append(new_tree)
                trees_placed += 1
        
        # Add natural mud puddles (avoiding river)
        mud_puddles_placed = 0
        attempts = 0
        max_attempts = 500  # Prevent infinite loop
        while mud_puddles_placed < 8 and attempts < max_attempts:
            attempts += 1
            new_puddle = MudPuddle(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50)
            )
            # Check if puddle overlaps with river
            if not new_puddle.overlaps_river(self.river_segments):
                self.mud_puddles.append(new_puddle)
                mud_puddles_placed += 1
        
        # Add herbivores
        for _ in range(30):  # 2x more than before (was 15)
            self.animals.append(Animal(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50),
                AnimalType.HERBIVORE
            ))
        
        # Add carnivores (2x more - 12 instead of 6)
        for _ in range(12):
            self.animals.append(Animal(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50),
                AnimalType.CARNIVORE
            ))
        
        # Don't spawn alpha predators at beginning - they can spawn later if needed
        
        # Add decomposers
        for _ in range(10):
            self.animals.append(Animal(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50),
                AnimalType.DECOMPOSER
            ))
        
        # Add tree eaters (half the amount at beginning)
        for _ in range(16):  # Halved from 32 to 16
            self.animals.append(Animal(
                random.uniform(50, self.window_width - 50),
                random.uniform(50, self.window_height - 50),
                AnimalType.TREE_EATER
            ))
    
    def handle_events(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize - allow any size (with very small minimum to prevent crashes)
                new_width = max(50, event.w)  # Very small minimum to prevent crashes
                new_height = max(50, event.h)  # Very small minimum to prevent crashes
                
                # Calculate scale factors
                scale_x = new_width / self.window_width if self.window_width > 0 else 1.0
                scale_y = new_height / self.window_height if self.window_height > 0 else 1.0
                
                # Update window size
                self.window_width = new_width
                self.window_height = new_height
                
                # Resize screen with hardware acceleration
                flags = pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE
                if hasattr(pygame, 'SCALED'):
                    flags |= pygame.SCALED
                try:
                    self.screen = pygame.display.set_mode((self.window_width, self.window_height), flags)
                except:
                    # Fallback if resize fails
                    self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
                
                # Scale all entity positions
                self.scale_entities(scale_x, scale_y)
                
                # Update UI element positions
                self.graph_min_width = max(50, self.window_width // 2)  # Ensure minimum
                self.graph_max_width = max(100, self.window_width - 20)  # Ensure minimum
                # Clamp current graph width to new limits
                self.graph_width = max(self.graph_min_width, min(self.graph_max_width, self.graph_width))
                self.stats_panel_rect = pygame.Rect(max(0, self.window_width - 250), 10, 240, 30)
            
            elif event.type == pygame.KEYDOWN:
                # Toggle stats panel
                if event.key == pygame.K_TAB:
                    self.stats_panel_open = not self.stats_panel_open
                
                # Speed control
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    idx = self.speed_options.index(self.speed_multiplier)
                    if idx < len(self.speed_options) - 1:
                        self.speed_multiplier = self.speed_options[idx + 1]
                elif event.key == pygame.K_MINUS:
                    idx = self.speed_options.index(self.speed_multiplier)
                    if idx > 0:
                        self.speed_multiplier = self.speed_options[idx - 1]
                elif event.key == pygame.K_0:
                    self.speed_multiplier = 1
                
                # Tool selection (legacy keys)
                if event.key == pygame.K_1:
                    self.selected_tool = "tree"
                elif event.key == pygame.K_2:
                    self.selected_tool = "herbivore"
                elif event.key == pygame.K_3:
                    self.selected_tool = "tree_eater"
                elif event.key == pygame.K_4:
                    self.selected_tool = "carnivore"
                elif event.key == pygame.K_5:
                    self.selected_tool = "decomposer"
                elif event.key == pygame.K_6:
                    self.selected_tool = "wall"
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check if clicking graph resize handle (check this FIRST before other UI elements)
                    graph_x = 10
                    graph_y = self.window_height - 160
                    graph_height = 150
                    # Match the exact handle position from draw function - make it easier to click (full height)
                    resize_handle_rect = pygame.Rect(graph_x + self.graph_width - 15, graph_y, 15, graph_height)
                    resize_clicked = False
                    if resize_handle_rect.collidepoint(mouse_x, mouse_y):
                        self.graph_resizing = True
                        # Store the graph's right edge position and mouse position
                        self.graph_resize_anchor_x = graph_x + self.graph_width
                        self.graph_resize_mouse_start_x = mouse_x
                        resize_clicked = True
                    
                    # Only process other click events if resize handle wasn't clicked
                    if not resize_clicked:
                        # Check if clicking stats panel toggle
                        toggle_rect = pygame.Rect(self.stats_panel_rect.x, self.stats_panel_rect.y, 
                                                 self.stats_panel_rect.width, 30)
                        if toggle_rect.collidepoint(mouse_x, mouse_y):
                            self.stats_panel_open = not self.stats_panel_open
                        # Check if clicking dropdown
                        elif self.dropdown_rect.collidepoint(mouse_x, mouse_y):
                            self.dropdown_open = not self.dropdown_open
                        elif self.dropdown_open:
                            # Check if clicking dropdown option
                            dropdown_y = self.dropdown_rect.bottom
                            for i, (name, tool, color) in enumerate(self.dropdown_options):
                                option_rect = pygame.Rect(self.dropdown_rect.x, dropdown_y + i * self.dropdown_item_height,
                                                         self.dropdown_rect.width, self.dropdown_item_height)
                                if option_rect.collidepoint(mouse_x, mouse_y):
                                    self.selected_tool = tool
                                    self.dropdown_open = False
                                    break
                            else:
                                self.dropdown_open = False
                        else:
                            # Check if pointer tool is selected
                            if self.selected_tool == "pointer":
                                # Find entity at click position
                                self.selected_entity = self.find_entity_at(mouse_x, mouse_y)
                            else:
                                # Spawn entity
                                self.spawn_entity(mouse_x, mouse_y)
                                self.mouse_held = True
                                self.mouse_hold_timer = 0
                
                elif event.button == 3:  # Right click - cancel wall placement
                    self.wall_start = None
                    self.dropdown_open = False
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.mouse_held = False
                    self.mouse_hold_timer = 0
                    self.graph_resizing = False
        
        # Handle graph resizing - completely rewritten for smooth resizing
        if self.graph_resizing:
            # Calculate how far the mouse has moved from where we started
            mouse_delta = mouse_x - self.graph_resize_mouse_start_x
            # The new right edge position is the anchor + mouse movement
            new_right_edge = self.graph_resize_anchor_x + mouse_delta
            # Graph starts at x=10, so width = right_edge - 10
            new_width = new_right_edge - 10
            # Clamp to min/max width
            self.graph_width = max(self.graph_min_width, min(self.graph_max_width, new_width))
        
        # Handle mouse hold for continuous spawning
        if self.mouse_held and not self.dropdown_open and self.selected_tool != "pointer":
            self.mouse_hold_timer += 1
            if self.mouse_hold_timer > 5:  # Spawn every 5 frames when held
                self.spawn_entity(mouse_x, mouse_y)
                self.mouse_hold_timer = 0
    
    def spawn_entity(self, mouse_x: int, mouse_y: int):
        if self.selected_tool == "tree":
            self.trees.append(Tree(mouse_x, mouse_y))
            self.stats['trees_planted'] += 1
        elif self.selected_tool == "herbivore":
            self.animals.append(Animal(mouse_x, mouse_y, AnimalType.HERBIVORE))
            self.stats['herbivores_born'] += 1
        elif self.selected_tool == "tree_eater":
            self.animals.append(Animal(mouse_x, mouse_y, AnimalType.TREE_EATER))
            self.stats['tree_eaters_born'] += 1
        elif self.selected_tool == "carnivore":
            self.animals.append(Animal(mouse_x, mouse_y, AnimalType.CARNIVORE))
            self.stats['carnivores_born'] += 1
        elif self.selected_tool == "decomposer":
            self.animals.append(Animal(mouse_x, mouse_y, AnimalType.DECOMPOSER))
            self.stats['decomposers_born'] += 1
        elif self.selected_tool == "alpha_predator":
            self.animals.append(Animal(mouse_x, mouse_y, AnimalType.ALPHA_PREDATOR))
        elif self.selected_tool == "wall":
            if self.wall_start is None:
                self.wall_start = (mouse_x, mouse_y)
            else:
                self.walls.append(Wall(self.wall_start[0], self.wall_start[1], 
                                      mouse_x, mouse_y))
                self.wall_start = None
    
    def find_entity_at(self, x: float, y: float):
        """Find the entity at the given position (prioritize animals, then trees, then others)"""
        # Check animals first (they're on top)
        for animal in self.animals:
            if animal.alive:
                dist = math.sqrt((animal.x - x)**2 + (animal.y - y)**2)
                if dist <= animal.size:
                    return animal
        
        # Check trees
        for tree in self.trees:
            if tree.alive:
                dist = math.sqrt((tree.x - x)**2 + (tree.y - y)**2)
                if dist <= tree.size:
                    return tree
        
        # Check dead bodies
        for body in self.dead_bodies:
            if body.alive:
                dist = math.sqrt((body.x - x)**2 + (body.y - y)**2)
                if dist <= body.size:
                    return body
        
        # Check seeds
        for seed in self.seeds:
            if seed.alive:
                dist = math.sqrt((seed.x - x)**2 + (seed.y - y)**2)
                if dist <= seed.size:
                    return seed
        
        # Check mud puddles
        for puddle in self.mud_puddles:
            if puddle.contains_point(x, y):
                return puddle
        
        # Check caves
        for cave in self.caves:
            if cave.contains_point(x, y):
                return cave
        
        return None
    
    def update(self):
        # Run multiple updates based on speed multiplier
        # Increment update counter for tracking
        if not hasattr(self, 'update_counter'):
            self.update_counter = 0
        self.update_counter += 1
        
        for _ in range(self.speed_multiplier):
            # Update seeds first (they can fertilize trees)
            for seed in self.seeds:
                if seed.alive:
                    was_alive = seed.alive
                    seed.update(self.trees)
                    if not seed.alive and was_alive:
                        if hasattr(seed, 'fertilized') and seed.fertilized:
                            self.stats['seeds_fertilized'] += 1
                        else:
                            self.stats['seeds_eaten'] += 1
                    # Track seed dispersal
                    if hasattr(seed, 'tracked_dispersed') and seed.tracked_dispersed:
                        self.stats['seeds_dispersed'] = self.stats.get('seeds_dispersed', 0) + 1
                        seed.tracked_dispersed = False
                    
                    # Check if seed can grow into tree (1/5 chance for seeds from fruit)
                    if hasattr(seed, 'can_grow_tree') and seed.can_grow_tree:
                        # Create a new tree from the seed
                        new_tree = Tree(seed.x + random.uniform(-10, 10), 
                                       seed.y + random.uniform(-10, 10))
                        # Check for tree overlap before adding
                        can_place = True
                        for existing_tree in self.trees:
                            if existing_tree.alive:
                                # Use squared distance to avoid sqrt
                                dx = new_tree.x - existing_tree.x
                                dy = new_tree.y - existing_tree.y
                                dist_sq = dx*dx + dy*dy
                                min_dist_sq = ((new_tree.size + existing_tree.size) / 2) ** 2
                                if dist_sq < min_dist_sq:
                                    can_place = False
                                    break
                        
                        if can_place:
                            self.trees.append(new_tree)
                            new_tree.tracked_from_seed = True
                            seed.alive = False  # Remove seed
                            self.stats['trees_planted'] += 1
                            self.stats['seeds_grown_trees'] = self.stats.get('seeds_grown_trees', 0) + 1
                        seed.can_grow_tree = False  # Reset flag
            
            # Seeds now grow into trees on their own (handled in seed.update)
            
            # Update trees (they check for fertilization from seeds and dead trees)
            # Get dead trees from previous cycle (before updating)
            dead_trees_prev = [t for t in self.trees if not t.alive]
            for tree in self.trees:
                if tree.alive:
                    tree.update(self.seeds, self.dead_bodies, dead_trees_prev)
                    if not tree.alive:
                        # Track tree death reason
                        if hasattr(tree, 'death_reason'):
                            if tree.death_reason == "fertilization":
                                self.stats['trees_died_fertilization'] += 1
                            elif tree.death_reason == "eaten":
                                self.stats['trees_died_eaten'] += 1
                        else:
                            self.stats['trees_died_age'] += 1
            
            # Build spatial grid for efficient queries
            self.spatial_grid.clear()
            for animal in self.animals:
                if animal.alive:
                    self.spatial_grid.add(animal)
            for body in self.dead_bodies:
                if body.alive:
                    self.spatial_grid.add(body)
            for seed in self.seeds:
                if seed.alive:
                    self.spatial_grid.add(seed)
            
            # Update animals with optimized neighbor queries
            # Process animals in batches for better cache performance
            alive_animals = [a for a in self.animals if a.alive]
            for animal in alive_animals:
                animal.update(self.trees, self.animals, self.dead_bodies, 
                             self.river_segments, self.walls, self.seeds, self.spatial_grid,
                             self.mud_puddles, self.window_width, self.window_height)
            
            # Create dead bodies from dead animals (before cleanup)
            dead_animals = []
            for animal in self.animals:
                if not animal.alive:
                    dead_animals.append(animal)
                    self.dead_bodies.append(DeadBody(animal.x, animal.y))
                    # Track animal deaths
                    if animal.type == AnimalType.HERBIVORE:
                        self.stats['herbivores_died'] += 1
                    elif animal.type == AnimalType.CARNIVORE:
                        self.stats['carnivores_died'] += 1
                    elif animal.type == AnimalType.DECOMPOSER:
                        self.stats['decomposers_died'] += 1
                    elif animal.type == AnimalType.TREE_EATER:
                        self.stats['tree_eaters_died'] += 1
            
            # Update dead bodies
            for body in self.dead_bodies:
                if body.alive:
                    body.update()
            
            # Seeds are updated earlier in the loop (before trees)
            
            # Clean up dead entities (more efficient - only when needed)
            if dead_animals or any(not t.alive for t in self.trees) or any(not b.alive for b in self.dead_bodies):
                self.animals = [a for a in self.animals if a.alive]
                self.trees = [t for t in self.trees if t.alive]
                self.dead_bodies = [b for b in self.dead_bodies if b.alive]
                self.seeds = [s for s in self.seeds if s.alive]
            
            # Apply ecological balance mechanisms
            self.apply_ecological_balance()
            
            # Update population history for graph
            self.population_update_counter += 1
            if self.population_update_counter >= self.population_update_interval:
                self.population_update_counter = 0
                self.update_population_history()
        
        self.update_counter += 1
    
    def apply_ecological_balance(self):
        """Apply ecological balance mechanisms inspired by natural ecosystems"""
        # Resource competition - if too few trees per herbivore, herbivores struggle
        herbivore_count = sum(1 for a in self.animals if a.type == AnimalType.HERBIVORE and a.alive)
        total_trees = len([t for t in self.trees if t.alive])
        if herbivore_count > 0 and total_trees > 0:
            trees_per_herbivore = total_trees / herbivore_count
            if trees_per_herbivore < 0.5:  # Less than 0.5 trees per herbivore
                # Herbivores lose hunger faster (competition)
                for animal in self.animals:
                    if animal.type == AnimalType.HERBIVORE and animal.alive:
                        animal.health -= 0.01  # Extra health loss from competition
        
        # Predator-prey balance - if too many predators, prey populations crash
        carnivore_count = sum(1 for a in self.animals if a.type == AnimalType.CARNIVORE and a.alive)
        prey_count = herbivore_count + sum(1 for a in self.animals if a.type == AnimalType.TREE_EATER and a.alive)
        if carnivore_count > 0 and prey_count > 0:
            prey_per_predator = prey_count / carnivore_count
            if prey_per_predator < 3:  # Less than 3 prey per predator
                # Predators have harder time finding food (health decays faster)
                for animal in self.animals:
                    if animal.type == AnimalType.CARNIVORE and animal.alive:
                        animal.health -= 0.01  # Extra health loss from competition
                        # Ensure health doesn't go below 0 (death is handled when health <= 0)
                        if animal.health < 0:
                            animal.health = 0
    
    def update_population_history(self):
        """Update population history with current percentages"""
        # Count current populations (including trees)
        herbivore_count = sum(1 for a in self.animals if a.type == AnimalType.HERBIVORE and a.alive)
        tree_eater_count = sum(1 for a in self.animals if a.type == AnimalType.TREE_EATER and a.alive)
        carnivore_count = sum(1 for a in self.animals if a.type == AnimalType.CARNIVORE and a.alive)
        decomposer_count = sum(1 for a in self.animals if a.type == AnimalType.DECOMPOSER and a.alive)
        alpha_count = sum(1 for a in self.animals if a.type == AnimalType.ALPHA_PREDATOR and a.alive)
        tree_count = sum(1 for t in self.trees if t.alive)
        
        total = herbivore_count + tree_eater_count + carnivore_count + decomposer_count + alpha_count + tree_count
        
        # Stop updating if no animals or trees are alive
        if total == 0:
            return
        
        if total > 0:
            # Calculate percentages
            herbivore_pct = (herbivore_count / total) * 100
            tree_eater_pct = (tree_eater_count / total) * 100
            carnivore_pct = (carnivore_count / total) * 100
            decomposer_pct = (decomposer_count / total) * 100
            alpha_pct = (alpha_count / total) * 100
            tree_pct = (tree_count / total) * 100
        else:
            # No entities, all percentages are 0
            herbivore_pct = tree_eater_pct = carnivore_pct = decomposer_pct = alpha_pct = tree_pct = 0
        
        # Add to history
        self.population_history.append({
            'herbivore': herbivore_pct,
            'tree_eater': tree_eater_pct,
            'carnivore': carnivore_pct,
            'decomposer': decomposer_pct,
            'alpha': alpha_pct,
            'tree': tree_pct
        })
        
        # Keep only last N entries
        if len(self.population_history) > self.max_history_length:
            self.population_history.pop(0)
    
    def draw_population_graph(self):
        """Draw a stacked bar chart showing population percentages over time"""
        if len(self.population_history) < 2:
            return  # Need at least 2 data points
        
        # Check if any animals or trees are alive - if not, don't draw graph
        total_alive = sum(1 for a in self.animals if a.alive) + sum(1 for t in self.trees if t.alive)
        if total_alive == 0:
            return
        
        # Graph dimensions (bottom left)
        graph_x = 10
        graph_y = self.window_height - 160  # Bottom left with padding
        graph_height = 150
        
        # Draw background
        pygame.draw.rect(self.screen, (240, 240, 240), 
                        (graph_x, graph_y, self.graph_width, graph_height))
        pygame.draw.rect(self.screen, BLACK, 
                        (graph_x, graph_y, self.graph_width, graph_height), 2)
        
        # Draw title
        title_text = self.font.render("Population %", True, BLACK)
        self.screen.blit(title_text, (graph_x + 5, graph_y + 2))
        
        # Draw graph area (with some padding for title and resize handle)
        graph_area_x = graph_x + 5
        graph_area_y = graph_y + 25
        graph_area_width = self.graph_width - 20  # Leave space for resize handle
        graph_area_height = graph_height - 30
        
        # Draw each data point as a vertical stacked bar
        # Show ALL history - dynamically compress bars as more data accumulates
        num_points = len(self.population_history)
        if num_points > 1:
            # Calculate bar width to fit all data points
            bar_width = max(0.1, graph_area_width / num_points)  # Can be fractional for many points
            
            for i, data in enumerate(self.population_history):
                x = graph_area_x + i * bar_width
                y_bottom = int(graph_area_y + graph_area_height)
                current_y = y_bottom
                bar_w = max(1, int(bar_width))  # At least 1 pixel wide
                
                # Draw stacked segments (bottom to top)
                # Trees at the bottom (dark green)
                if data.get('tree', 0) > 0:
                    height = max(1, int((data['tree'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, DARK_GREEN,
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
                
                # Herbivores (green)
                if data['herbivore'] > 0:
                    height = max(1, int((data['herbivore'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, GREEN,
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
                
                # Tree eaters (orange)
                if data['tree_eater'] > 0:
                    height = max(1, int((data['tree_eater'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, ORANGE,
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
                
                # Carnivores (red)
                if data['carnivore'] > 0:
                    height = max(1, int((data['carnivore'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, RED,
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
                
                # Decomposers (purple)
                if data['decomposer'] > 0:
                    height = max(1, int((data['decomposer'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, PURPLE,
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
                
                # Alpha predators (dark red)
                if data['alpha'] > 0:
                    height = max(1, int((data['alpha'] / 100) * graph_area_height))
                    pygame.draw.rect(self.screen, (139, 0, 0),
                                   (int(x), current_y - height, bar_w, height))
                    current_y -= height
        
        # Draw resize handle (grip pattern on the right edge) - full height for easier clicking
        resize_handle_x = graph_x + self.graph_width - 15
        resize_handle_y = graph_y
        resize_handle_width = 15
        resize_handle_height = graph_height
        
        # Draw handle background with border
        handle_rect = pygame.Rect(resize_handle_x, resize_handle_y, resize_handle_width, resize_handle_height)
        pygame.draw.rect(self.screen, (240, 240, 240), handle_rect)
        pygame.draw.rect(self.screen, (150, 150, 150), handle_rect, 2)
        
        # Draw grip pattern: vertical lines spaced evenly (like |||)
        grip_x = resize_handle_x + resize_handle_width // 2
        num_grips = 5
        grip_spacing = resize_handle_height / (num_grips + 1)
        
        for i in range(1, num_grips + 1):
            y_pos = int(resize_handle_y + i * grip_spacing)
            # Draw a vertical grip line
            pygame.draw.line(self.screen, (100, 100, 100), 
                           (grip_x - 2, y_pos - 4), (grip_x - 2, y_pos + 4), 2)
            pygame.draw.line(self.screen, (100, 100, 100), 
                           (grip_x + 2, y_pos - 4), (grip_x + 2, y_pos + 4), 2)
        
        # Draw legend
        legend_y = graph_y + graph_height - 20
        legend_items = [
            ("H", GREEN),
            ("T", ORANGE),
            ("C", RED),
            ("D", PURPLE),
            ("A", (139, 0, 0)),
            ("Tr", DARK_GREEN)
        ]
        legend_x = graph_x + 5
        for i, (label, color) in enumerate(legend_items):
            pygame.draw.rect(self.screen, color, (legend_x + i * 40, legend_y, 12, 12))
            label_text = self.font.render(label, True, BLACK)
            self.screen.blit(label_text, (legend_x + i * 40 + 15, legend_y - 2))
    
    def draw_stats(self):
        # Count populations
        herbivore_count = sum(1 for a in self.animals if a.type == AnimalType.HERBIVORE)
        tree_eater_count = sum(1 for a in self.animals if a.type == AnimalType.TREE_EATER)
        carnivore_count = sum(1 for a in self.animals if a.type == AnimalType.CARNIVORE)
        decomposer_count = sum(1 for a in self.animals if a.type == AnimalType.DECOMPOSER)
        tree_count = sum(1 for t in self.trees if t.alive)
        dead_body_count = len(self.dead_bodies)
        
        # Draw stats panel
        stats_y = 10
        stats = [
            ("Trees", tree_count, None),
            ("Herbivores", herbivore_count, GREEN),
            ("Tree Eaters", tree_eater_count, ORANGE),
            ("Carnivores", carnivore_count, RED),
            ("Decomposers", decomposer_count, PURPLE),
            ("Dead Bodies", dead_body_count, None),
        ]
        
        for i, (name, count, color) in enumerate(stats):
            stat_text = f"{name}: {count}"
            text = self.font.render(stat_text, True, BLACK)
            # Draw background
            rect_width = text.get_width() + 30
            pygame.draw.rect(self.screen, WHITE, 
                           (10, stats_y + i * 25 - 2, rect_width, 24))
            # Draw color indicator
            if color:
                pygame.draw.rect(self.screen, color,
                               (12, stats_y + i * 25, 15, 15))
            self.screen.blit(text, (30, stats_y + i * 25))
        
        # Speed indicator
        speed_text = f"Speed: {self.speed_multiplier}x (+/- to change)"
        text = self.font.render(speed_text, True, BLACK)
        pygame.draw.rect(self.screen, WHITE,
                       (10, stats_y + len(stats) * 25, text.get_width() + 4, 24))
        self.screen.blit(text, (12, stats_y + len(stats) * 25))
        
        # Controls
        controls_y = stats_y + (len(stats) + 1) * 25
        control_texts = [
            "Use dropdown to select tool",
            "Click/Hold to spawn",
            "Right-click to cancel wall"
        ]
        for i, ctrl in enumerate(control_texts):
            text = self.font.render(ctrl, True, BLACK)
            pygame.draw.rect(self.screen, WHITE,
                           (10, controls_y + i * 25, text.get_width() + 4, 24))
            self.screen.blit(text, (12, controls_y + i * 25))
    
    def draw_dropdown(self):
        # Draw dropdown button
        pygame.draw.rect(self.screen, WHITE, self.dropdown_rect)
        pygame.draw.rect(self.screen, BLACK, self.dropdown_rect, 2)
        
        # Find selected option name
        selected_name = "Select Tool"
        selected_color = None
        for name, tool, color in self.dropdown_options:
            if tool == self.selected_tool:
                selected_name = name
                selected_color = color
                break
        
        # Draw selected option with color indicator
        if selected_color:
            pygame.draw.rect(self.screen, selected_color,
                           (self.dropdown_rect.x + 2, self.dropdown_rect.y + 2, 15, 21))
        text = self.font.render(selected_name, True, BLACK)
        self.screen.blit(text, (self.dropdown_rect.x + 20, self.dropdown_rect.y + 2))
        
        # Draw RTX status next to dropdown
        rtx_x = self.dropdown_rect.right + 10
        rtx_y = self.dropdown_rect.y  # Same vertical position as dropdown
        
        # Check RTX status (re-check periodically for accuracy)
        if not hasattr(self, 'rtx_check_counter'):
            self.rtx_check_counter = 0
        self.rtx_check_counter += 1
        if self.rtx_check_counter > 300:  # Re-check every 5 seconds at 60 FPS
            self.rtx_active, self.rtx_gpu_usage = self.detect_nvidia_rtx()
            self.rtx_check_counter = 0
        
        # Only show RTX ON if GPU usage is 30% or higher
        if self.rtx_active and self.rtx_gpu_usage >= 30.0:
            rtx_text = "RTX ON"
            rtx_color = (0, 200, 0)  # Slightly darker green for better contrast
        else:
            rtx_text = "RTX OFF"
            rtx_color = (200, 0, 0)  # Slightly darker red for better contrast
        
        # Create RTX rect matching dropdown size and style
        rtx_rect = pygame.Rect(rtx_x, rtx_y, self.dropdown_rect.width, self.dropdown_rect.height)
        
        # Draw RTX status with matching dropdown styling
        pygame.draw.rect(self.screen, WHITE, rtx_rect)
        pygame.draw.rect(self.screen, BLACK, rtx_rect, 2)
        
        # Render text with black outline effect
        rtx_surface = self.font.render(rtx_text, True, rtx_color)
        
        # Calculate centered position
        text_x = rtx_rect.x + (rtx_rect.width - rtx_surface.get_width()) // 2
        text_y = rtx_rect.y + (rtx_rect.height - rtx_surface.get_height()) // 2
        
        # Draw text with black outline (shadow effect for better visibility)
        outline_surface = self.font.render(rtx_text, True, BLACK)
        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            self.screen.blit(outline_surface, (text_x + dx, text_y + dy))
        # Draw main text on top
        self.screen.blit(rtx_surface, (text_x, text_y))
        
        # Draw dropdown menu if open
        if self.dropdown_open:
            menu_height = len(self.dropdown_options) * self.dropdown_item_height
            menu_rect = pygame.Rect(self.dropdown_rect.x, self.dropdown_rect.bottom,
                                   self.dropdown_rect.width, menu_height)
            pygame.draw.rect(self.screen, WHITE, menu_rect)
            pygame.draw.rect(self.screen, BLACK, menu_rect, 2)
            
            for i, (name, tool, color) in enumerate(self.dropdown_options):
                item_rect = pygame.Rect(menu_rect.x, menu_rect.y + i * self.dropdown_item_height,
                                       menu_rect.width, self.dropdown_item_height)
                
                # Highlight if selected
                if tool == self.selected_tool:
                    pygame.draw.rect(self.screen, (200, 200, 200), item_rect)
                
                # Draw color indicator
                if color:
                    pygame.draw.rect(self.screen, color,
                                   (item_rect.x + 2, item_rect.y + 2, 15, 21))
                
                # Draw text
                text = self.font.render(name, True, BLACK)
                self.screen.blit(text, (item_rect.x + 20, item_rect.y + 2))
    
    def draw_detailed_stats_panel(self):
        """Draw collapsible detailed stats panel on the right side"""
        # Draw toggle button
        toggle_rect = pygame.Rect(self.stats_panel_rect.x, self.stats_panel_rect.y, 
                                 self.stats_panel_rect.width, 30)
        pygame.draw.rect(self.screen, WHITE, toggle_rect)
        pygame.draw.rect(self.screen, BLACK, toggle_rect, 2)
        
        # Draw toggle text
        toggle_text = "Stats (TAB)" if not self.stats_panel_open else "Stats (TAB) -"
        text = self.font.render(toggle_text, True, BLACK)
        self.screen.blit(text, (toggle_rect.x + 5, toggle_rect.y + 3))
        
        if self.stats_panel_open:
            # Draw expanded panel
            panel_rect = pygame.Rect(self.stats_panel_rect.x, toggle_rect.bottom, 
                                    self.stats_panel_rect.width, self.stats_panel_expanded_height)
            pygame.draw.rect(self.screen, WHITE, panel_rect)
            pygame.draw.rect(self.screen, BLACK, panel_rect, 2)
            
            # Calculate ecological balance metrics
            current_herbivores = sum(1 for a in self.animals if a.type == AnimalType.HERBIVORE and a.alive)
            current_trees = sum(1 for t in self.trees if t.alive)
            current_carnivores = sum(1 for a in self.animals if a.type == AnimalType.CARNIVORE and a.alive)
            current_decomposers = sum(1 for a in self.animals if a.type == AnimalType.DECOMPOSER and a.alive)
            
            # Calculate birth/death ratios
            herbivore_ratio = (self.stats['herbivores_born'] / max(1, self.stats['herbivores_died'])) if self.stats['herbivores_died'] > 0 else float('inf')
            tree_ratio = (self.stats['trees_planted'] / max(1, self.stats['trees_died_fertilization'] + self.stats['trees_died_eaten'] + self.stats['trees_died_age'])) if (self.stats['trees_died_fertilization'] + self.stats['trees_died_eaten'] + self.stats['trees_died_age']) > 0 else float('inf')
            
            # Calculate seed efficiency
            seed_fert_rate = (self.stats['seeds_fertilized'] / max(1, self.stats['seeds_created'])) * 100 if self.stats['seeds_created'] > 0 else 0
            
            # Stats to display
            y_offset = 5
            stats_lines = [
                "=== TREES ===",
                f"Planted: {self.stats['trees_planted']}",
                f"Died (age): {self.stats['trees_died_age']}",
                f"Died (no fert): {self.stats['trees_died_fertilization']}",
                f"Died (eaten): {self.stats['trees_died_eaten']}",
                f"Current: {current_trees}",
                "",
                "=== HERBIVORES ===",
                f"Born: {self.stats['herbivores_born']}",
                f"Died: {self.stats['herbivores_died']}",
                f"Current: {current_herbivores}",
                f"B/D Ratio: {herbivore_ratio:.2f}" if herbivore_ratio != float('inf') else "B/D Ratio: N/A",
                "",
                "=== CARNIVORES ===",
                f"Born: {self.stats['carnivores_born']}",
                f"Died: {self.stats['carnivores_died']}",
                f"Current: {current_carnivores}",
                "",
                "=== DECOMPOSERS ===",
                f"Born: {self.stats['decomposers_born']}",
                f"Died: {self.stats['decomposers_died']}",
                f"Current: {current_decomposers}",
                "",
                "=== SEEDS ===",
                f"Created: {self.stats['seeds_created']}",
                f"Dispersed: {self.stats.get('seeds_dispersed', 0)}",
                f"Grown Trees: {self.stats.get('seeds_grown_trees', 0)}",
                f"Fertilized: {self.stats['seeds_fertilized']}",
                f"Eaten: {self.stats['seeds_eaten']}",
                f"Fert Rate: {seed_fert_rate:.1f}%",
                "",
                "=== MATING ===",
                f"Attempts: {self.stats['mating_attempts']}",
                f"Successful: {self.stats['mating_successful']}",
                f"Offspring: {self.stats['offspring_born']}",
                "",
                "=== EVENTS ===",
                f"Predator Fights: {self.stats.get('predator_fights', 0)}",
                f"Hibernation Entries: {self.stats.get('hibernation_entries', 0)}",
                f"Hibernation Exits: {self.stats.get('hibernation_exits', 0)}",
                f"Alpha Predators: {self.stats.get('alpha_predators_spawned', 0)}",
            ]
            
            for line in stats_lines:
                if line:
                    text = self.font.render(line, True, BLACK)
                    self.screen.blit(text, (panel_rect.x + 5, panel_rect.y + y_offset))
                y_offset += 20
                
                # Stop if we run out of space
                if y_offset > self.stats_panel_expanded_height - 10:
                    break
    
    def draw_entity_stats(self):
        """Draw stats panel for selected entity - follows entity position"""
        if not self.selected_entity:
            return
        
        # Check if entity is still alive/valid
        if hasattr(self.selected_entity, 'alive') and not self.selected_entity.alive:
            self.selected_entity = None
            return
        
        # Position panel near entity (top right of entity)
        entity_x = self.selected_entity.x
        entity_y = self.selected_entity.y
        entity_size = getattr(self.selected_entity, 'size', 10)
        
        # Panel dimensions
        panel_width = 220
        panel_height = 180
        
        # Position to top-right of entity with offset
        panel_x = int(entity_x + entity_size + 10)
        panel_y = int(entity_y - panel_height - 10)
        
        # Keep panel on screen
        panel_x = min(panel_x, self.window_width - panel_width - 10)
        panel_x = max(10, panel_x)
        panel_y = max(10, panel_y)
        if panel_y + panel_height > self.window_height:
            panel_y = self.window_height - panel_height - 10
        
        # Draw background
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(self.screen, (240, 240, 240), panel_rect)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 2)
        
        # Draw line connecting to entity
        pygame.draw.line(self.screen, (200, 200, 200), 
                        (int(entity_x), int(entity_y)), 
                        (panel_x, panel_y + panel_height // 2), 1)
        
        # Determine entity type and get stats
        y_offset = panel_y + 10
        
        if isinstance(self.selected_entity, Animal):
            animal = self.selected_entity
            type_names = {
                AnimalType.HERBIVORE: "Herbivore",
                AnimalType.TREE_EATER: "Tree Eater",
                AnimalType.CARNIVORE: "Carnivore",
                AnimalType.DECOMPOSER: "Decomposer",
                AnimalType.ALPHA_PREDATOR: "Alpha Predator"
            }
            
            # Draw type name
            type_text = self.font.render(type_names.get(animal.type, "Unknown"), True, BLACK)
            self.screen.blit(type_text, (panel_x + 10, y_offset))
            y_offset += 25
            
            # Draw visual health bar
            health_ratio = animal.health / animal.max_health
            bar_width = 180
            bar_height = 12
            bar_x = panel_x + 10
            bar_y = y_offset
            
            # Background (gray)
            pygame.draw.rect(self.screen, (200, 200, 200), 
                          (bar_x, bar_y, bar_width, bar_height))
            # Health (green to red gradient)
            health_color = (
                int(255 * (1 - health_ratio)),
                int(255 * health_ratio),
                0
            )
            pygame.draw.rect(self.screen, health_color, 
                          (bar_x, bar_y, int(bar_width * health_ratio), bar_height))
            # Border
            pygame.draw.rect(self.screen, BLACK, 
                          (bar_x, bar_y, bar_width, bar_height), 1)
            
            # Health text
            health_text = f"{int(health_ratio * 100)}%"
            text = self.font.render(health_text, True, BLACK)
            self.screen.blit(text, (bar_x + bar_width + 5, bar_y - 2))
            y_offset += 25
            
            # Status
            if animal.mating:
                status_text = "MATING"
            elif animal.is_idle:
                status_text = "IDLE"
            else:
                status_text = "HUNGRY"
            text = self.font.render(status_text, True, BLACK)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            
            # Type-specific info
            if animal.type == AnimalType.HERBIVORE:
                seed_text = f"{animal.carried_seeds}"
                text = self.font.render(seed_text, True, BLACK)
                self.screen.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
            
            # Conditions
            if animal.in_river:
                text = self.font.render("In River", True, BLUE)
                self.screen.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
            if animal.in_mud:
                text = self.font.render("In Mud", True, BROWN)
                self.screen.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
        
        elif isinstance(self.selected_entity, Tree):
            tree = self.selected_entity
            # Type
            text = self.font.render("Tree", True, DARK_GREEN)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            
            # Health bar
            health_ratio = tree.health / tree.max_health
            bar_width = 180
            bar_height = 12
            bar_x = panel_x + 10
            bar_y = y_offset
            
            pygame.draw.rect(self.screen, (200, 200, 200), 
                          (bar_x, bar_y, bar_width, bar_height))
            health_color = (
                int(255 * (1 - health_ratio)),
                int(255 * health_ratio),
                0
            )
            pygame.draw.rect(self.screen, health_color, 
                          (bar_x, bar_y, int(bar_width * health_ratio), bar_height))
            pygame.draw.rect(self.screen, BLACK, 
                          (bar_x, bar_y, bar_width, bar_height), 1)
            
            health_text = f"{int(health_ratio * 100)}%"
            text = self.font.render(health_text, True, BLACK)
            self.screen.blit(text, (bar_x + bar_width + 5, bar_y - 2))
            y_offset += 25
            
            # Fruit count
            fruit_text = f"{tree.fruit_count}"
            text = self.font.render(fruit_text, True, ORANGE)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
        
        elif isinstance(self.selected_entity, DeadBody):
            body = self.selected_entity
            text = self.font.render("Dead Body", True, DARK_GRAY)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            
            decay_text = f"Decay: {body.decay_time}"
            text = self.font.render(decay_text, True, BLACK)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
            
            if body.being_decomposed:
                text = self.font.render("Being Decomposed", True, PURPLE)
                self.screen.blit(text, (panel_x + 10, y_offset))
        
        elif isinstance(self.selected_entity, Seed):
            seed = self.selected_entity
            text = self.font.render("Seed", True, BROWN)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            
            if hasattr(seed, 'from_fruit') and seed.from_fruit:
                text = self.font.render("From Fruit", True, ORANGE)
                self.screen.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
            
            if hasattr(seed, 'can_grow_tree') and seed.can_grow_tree:
                text = self.font.render("Can Grow", True, GREEN)
                self.screen.blit(text, (panel_x + 10, y_offset))
        
        elif isinstance(self.selected_entity, MudPuddle):
            puddle = self.selected_entity
            text = self.font.render("Mud Puddle", True, BROWN)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            text = self.font.render("40%", True, BLACK)
            self.screen.blit(text, (panel_x + 10, y_offset))
        
        elif isinstance(self.selected_entity, Cave):
            cave = self.selected_entity
            text = self.font.render("Cave", True, DARK_GRAY)
            self.screen.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            text = self.font.render("Safe Zone", True, GREEN)
            self.screen.blit(text, (panel_x + 10, y_offset))
    
    def draw(self):
        # Skip rendering frames at very high speeds for performance
        should_render = True
        if self.speed_multiplier >= 10:
            # Render every Nth frame at high speeds
            render_interval = max(1, self.speed_multiplier // 10)
            should_render = (self.update_counter % render_interval == 0)
        
        if should_render:
            self.screen.fill(LIGHT_BLUE)  # Sky/background
            
            # Draw river
            for segment in self.river_segments:
                segment.draw(self.screen)
            
            # Draw walls
            for wall in self.walls:
                wall.draw(self.screen)
            
            # Draw wall being placed
            if self.wall_start:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                pygame.draw.line(self.screen, DARK_GRAY, self.wall_start, 
                               (mouse_x, mouse_y), 5)
            
            # Optimized rendering - count entities for optimization decisions
            num_animals = sum(1 for a in self.animals if a.alive)
            num_trees = sum(1 for t in self.trees if t.alive)
            
            # Use simplified rendering when there are many entities
            use_simplified = num_animals > 50 or num_trees > 100
            
            # Draw dead bodies (with stink radius) - only on screen, skip stink at high speeds
            draw_stink = self.speed_multiplier < 50 and not use_simplified
            for body in self.dead_bodies:
                if body.alive and -50 <= body.x <= self.window_width + 50 and -50 <= body.y <= self.window_height + 50:
                    body.draw(self.screen, draw_stink=draw_stink)
            
            # Draw mud puddles (static, draw once)
            for puddle in self.mud_puddles:
                if -50 <= puddle.x <= self.window_width + 50 and -50 <= puddle.y <= self.window_height + 50:
                    puddle.draw(self.screen)
            
            # Draw trees - always draw fruits even in simplified mode
            if use_simplified:
                for tree in self.trees:
                    if tree.alive and 0 <= tree.x <= self.window_width and 0 <= tree.y <= self.window_height:
                        # Simplified: circle with tree's color
                        pygame.draw.circle(self.screen, tree.color, 
                                          (int(tree.x), int(tree.y)), int(tree.size/2))
                        # Still draw fruits even in simplified mode
                        if tree.fruit_count > 0:
                            fruit_angle = 0
                            fruit_spacing = 2 * math.pi / max(1, tree.fruit_count)
                            for i in range(tree.fruit_count):
                                fruit_radius = tree.size/2 - 6
                                fruit_x = tree.x + math.cos(fruit_angle) * fruit_radius
                                fruit_y = tree.y + math.sin(fruit_angle) * fruit_radius
                                pygame.draw.circle(self.screen, ORANGE, (int(fruit_x), int(fruit_y)), 5)
                                pygame.draw.circle(self.screen, YELLOW, (int(fruit_x), int(fruit_y)), 3)
                                fruit_angle += fruit_spacing
            else:
                for tree in self.trees:
                    if tree.alive and 0 <= tree.x <= self.window_width and 0 <= tree.y <= self.window_height:
                        tree.draw(self.screen)
            
            # Draw seeds - only if not too many
            if len(self.seeds) < 200:  # Only draw if reasonable number
                for seed in self.seeds:
                    if seed.alive and 0 <= seed.x <= self.window_width and 0 <= seed.y <= self.window_height:
                        seed.draw(self.screen)
            
            # Draw animals - optimized rendering
            if use_simplified or self.speed_multiplier >= 50:
                # Very simplified rendering - colored dots with direction indicators
                for animal in self.animals:
                    if animal.alive and 0 <= animal.x <= self.window_width and 0 <= animal.y <= self.window_height:
                        pygame.draw.circle(self.screen, animal.color, 
                                          (int(animal.x), int(animal.y)), animal.size)
                        # Draw two small black eyes (only if not too many animals)
                        if num_animals < 150:  # Skip eye rendering when too many animals
                            eye_offset = animal.size * 0.3
                            eye_size = max(2, int(animal.size * 0.2))
                            perp_angle = animal.angle + math.pi / 2
                            
                            # Left eye
                            left_eye_x = animal.x + math.cos(animal.angle) * (animal.size * 0.5) + math.cos(perp_angle) * eye_offset
                            left_eye_y = animal.y + math.sin(animal.angle) * (animal.size * 0.5) + math.sin(perp_angle) * eye_offset
                            pygame.draw.circle(self.screen, BLACK, (int(left_eye_x), int(left_eye_y)), eye_size)
                            
                            # Right eye
                            right_eye_x = animal.x + math.cos(animal.angle) * (animal.size * 0.5) - math.cos(perp_angle) * eye_offset
                            right_eye_y = animal.y + math.sin(animal.angle) * (animal.size * 0.5) - math.sin(perp_angle) * eye_offset
                            pygame.draw.circle(self.screen, BLACK, (int(right_eye_x), int(right_eye_y)), eye_size)
            else:
                # Full rendering but skip some details if many animals
                skip_details = num_animals > 30
                for animal in self.animals:
                    if animal.alive and 0 <= animal.x <= self.window_width and 0 <= animal.y <= self.window_height:
                        if skip_details:
                            # Draw animal with integrated beak but without health bar
                            pygame.draw.circle(self.screen, animal.color, 
                                              (int(animal.x), int(animal.y)), animal.size)
                            # Draw two small black eyes (skip if too many animals)
                            if num_animals < 150:
                                eye_offset = animal.size * 0.3
                                eye_size = max(2, int(animal.size * 0.2))
                                perp_angle = animal.angle + math.pi / 2
                                
                                # Left eye
                                left_eye_x = animal.x + math.cos(animal.angle) * (animal.size * 0.5) + math.cos(perp_angle) * eye_offset
                                left_eye_y = animal.y + math.sin(animal.angle) * (animal.size * 0.5) + math.sin(perp_angle) * eye_offset
                                pygame.draw.circle(self.screen, BLACK, (int(left_eye_x), int(left_eye_y)), eye_size)
                                
                                # Right eye
                                right_eye_x = animal.x + math.cos(animal.angle) * (animal.size * 0.5) - math.cos(perp_angle) * eye_offset
                                right_eye_y = animal.y + math.sin(animal.angle) * (animal.size * 0.5) - math.sin(perp_angle) * eye_offset
                                pygame.draw.circle(self.screen, BLACK, (int(right_eye_x), int(right_eye_y)), eye_size)
                            # Only draw mating heart if mating
                            if animal.mating:
                                heart_size = 3
                                heart_y = int(animal.y - animal.size - 5)
                                heart_points = [
                                    (int(animal.x - heart_size), int(heart_y)),
                                    (int(animal.x), int(heart_y - heart_size)),
                                    (int(animal.x + heart_size), int(heart_y)),
                                    (int(animal.x - heart_size), int(heart_y)),
                                    (int(animal.x), int(heart_y + heart_size)),
                                    (int(animal.x + heart_size), int(heart_y))
                                ]
                                pygame.draw.polygon(self.screen, RED, heart_points)
                        else:
                            animal.draw(self.screen)
        
        # Always draw UI
        self.draw_stats()
        self.draw_population_graph()
        self.draw_dropdown()
        self.draw_detailed_stats_panel()
        self.draw_entity_stats()
        
        # Update display - use flip() for double buffering (GPU accelerated)
        # flip() is more efficient with hardware acceleration as it uses GPU
        if self.use_dirty_rects and len(self.dirty_rects) > 0:
            # Update only dirty rectangles (more efficient)
            pygame.display.update(self.dirty_rects)
        else:
            # Full screen update - uses GPU double buffering
            pygame.display.flip()
    
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            # Adjust FPS based on speed (but cap it)
            target_fps = min(FPS * self.speed_multiplier, FPS * 10)
            self.clock.tick(target_fps)
        
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()

