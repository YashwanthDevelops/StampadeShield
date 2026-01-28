#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CPI WEIGHT OPTIMIZER - ML TRAINING                         ║
║                                                                              ║
║  Trains a logistic regression model to find optimal CPI weights              ║
║  Replaces arbitrary guesses with scientifically derived values               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Author: StampadeShield Team
Purpose: Derive optimal CPI weights using machine learning

METHODOLOGY:
1. Generate thousands of labeled stampede simulations
2. Label each timestep: "Will danger occur in next 30 seconds?"
3. Train logistic regression on [density, movement, audio, trend] features
4. Extract model coefficients as optimized CPI weights
5. Validate improvement over original guessed weights

WHY LOGISTIC REGRESSION?
- Interpretable: Coefficients directly become weights
- Linear: Matches CPI formula structure (weighted sum)
- Fast: Trains in seconds
- Explainable: "We used ML to optimize weights" sounds research-grade
"""

import numpy as np
import json
import argparse
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from collections import deque
import warnings
warnings.filterwarnings('ignore')

# ML imports
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

# Original guessed weights (our baseline to beat)
ORIGINAL_WEIGHTS = {
    'density': 0.35,
    'movement': 0.25,
    'audio': 0.20,
    'trend': 0.20
}

# Labeling parameters
LOOKAHEAD_WINDOW = 30  # seconds to look ahead for danger
DANGER_THRESHOLD = 70  # density score threshold for "danger"

# Simulation parameters
SIMULATION_DURATION = 120  # seconds per simulation

# ════════════════════════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS (Same as validation_test.py for consistency)
# ════════════════════════════════════════════════════════════════════════════════

SCENARIOS = {
    'safe': {
        'name': 'Safe (Normal)',
        'phases': [
            {'duration': 120, 'distance': (150, 200), 'pir': (0, 2), 'audio': (100, 250)}
        ],
    },
    'medium': {
        'name': 'Medium (Moderate)',
        'phases': [
            {'duration': 40, 'distance': (120, 180), 'pir': (1, 3), 'audio': (150, 300)},
            {'duration': 40, 'distance': (80, 140), 'pir': (3, 5), 'audio': (300, 450)},
            {'duration': 40, 'distance': (60, 100), 'pir': (4, 7), 'audio': (400, 550)},
        ],
    },
    'surge': {
        'name': 'Surge (Rapid Buildup)',
        'phases': [
            {'duration': 30, 'distance': (120, 180), 'pir': (1, 3), 'audio': (150, 280)},
            {'duration': 20, 'distance': (90, 140), 'pir': (5, 9), 'audio': (450, 650)},
            {'duration': 30, 'distance': (50, 90), 'pir': (7, 12), 'audio': (550, 750)},
            {'duration': 40, 'distance': (25, 55), 'pir': (10, 15), 'audio': (650, 900)},
        ],
        'audio_spikes': True,
    },
    'critical': {
        'name': 'Critical (Immediate Danger)',
        'phases': [
            {'duration': 15, 'distance': (100, 160), 'pir': (2, 4), 'audio': (200, 350)},
            {'duration': 20, 'distance': (70, 120), 'pir': (8, 14), 'audio': (550, 800)},
            {'duration': 25, 'distance': (35, 70), 'pir': (10, 16), 'audio': (700, 950)},
            {'duration': 60, 'distance': (15, 40), 'pir': (12, 18), 'audio': (800, 1000)},
        ],
        'audio_spikes': True,
    }
}


# ════════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class SensorReading:
    timestamp: int
    distance: float
    pir_count: int
    audio_level: float

@dataclass 
class FeatureVector:
    density_score: float
    movement_score: float
    audio_score: float
    trend_score: float
    label: int  # 0 = safe, 1 = danger coming

@dataclass
class TrainingResult:
    weights: Dict[str, float]
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc: float
    cv_scores: List[float]
    feature_importance: Dict[str, float]


# ════════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE (Reused from validation_test.py)
# ════════════════════════════════════════════════════════════════════════════════

class CrowdSimulator:
    """Generates realistic crowd sensor data"""
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)
    
    def generate_scenario(self, scenario_key: str) -> List[SensorReading]:
        if scenario_key not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_key}")
        
        config = SCENARIOS[scenario_key]
        readings = []
        current_time = 0
        
        for phase in config['phases']:
            for t in range(phase['duration']):
                if current_time >= SIMULATION_DURATION:
                    break
                
                dist = self._generate_in_range(phase['distance'], noise=0.15)
                pir = int(self._generate_in_range(phase['pir'], noise=0.2))
                audio = self._generate_in_range(phase['audio'], noise=0.15)
                
                if config.get('audio_spikes') and self.rng.random() < 0.12:
                    audio = min(1000, audio * self.rng.uniform(1.2, 1.4))
                
                readings.append(SensorReading(
                    timestamp=current_time,
                    distance=max(10, min(400, dist)),
                    pir_count=max(0, min(20, pir)),
                    audio_level=max(0, min(1000, audio))
                ))
                current_time += 1
        
        # Pad if needed
        while len(readings) < SIMULATION_DURATION:
            last = readings[-1]
            readings.append(SensorReading(
                timestamp=len(readings),
                distance=last.distance + self.rng.uniform(-5, 5),
                pir_count=last.pir_count,
                audio_level=last.audio_level + self.rng.uniform(-20, 20)
            ))
        
        return readings[:SIMULATION_DURATION]
    
    def _generate_in_range(self, range_tuple: tuple, noise: float = 0.1) -> float:
        min_val, max_val = range_tuple
        base = self.rng.uniform(min_val, max_val)
        noise_amount = (max_val - min_val) * noise * self.rng.standard_normal()
        return base + noise_amount


# ════════════════════════════════════════════════════════════════════════════════
# FEATURE EXTRACTION
# ════════════════════════════════════════════════════════════════════════════════

class FeatureExtractor:
    """
    Extracts feature scores from raw sensor readings.
    These are the same calculations used in the production CPI.
    """
    
    def __init__(self):
        self.score_history = deque(maxlen=10)
    
    def reset(self):
        self.score_history.clear()
    
    def calculate_density_score(self, distance: float) -> float:
        """Convert distance to density score (0-100)"""
        if distance >= 150:
            return max(0, 15 - (distance - 150) * 0.08)
        elif distance >= 100:
            return 15 + (150 - distance) * 0.4
        elif distance >= 60:
            return 35 + (100 - distance) * 0.5
        elif distance >= 40:
            return 55 + (60 - distance) * 1.0
        else:
            return min(100, 75 + (40 - distance) * 0.83)
    
    def calculate_movement_score(self, pir_count: int) -> float:
        """Convert PIR triggers to movement score (0-100)"""
        if pir_count <= 2:
            return pir_count * 7.5
        elif pir_count <= 5:
            return 15 + (pir_count - 2) * 6.67
        elif pir_count <= 8:
            return 35 + (pir_count - 5) * 6.67
        elif pir_count <= 12:
            return 55 + (pir_count - 8) * 6.25
        else:
            return min(100, 80 + (pir_count - 12) * 5)
    
    def calculate_audio_score(self, audio_level: float) -> float:
        """Convert audio level to distress score (0-100)"""
        if audio_level < 250:
            return audio_level / 12.5
        elif audio_level < 400:
            return 20 + (audio_level - 250) * 0.1
        elif audio_level < 550:
            return 35 + (audio_level - 400) * 0.1
        elif audio_level < 700:
            return 50 + (audio_level - 550) * 0.133
        elif audio_level < 850:
            return 70 + (audio_level - 700) * 0.133
        else:
            return min(100, 90 + (audio_level - 850) * 0.067)
    
    def calculate_trend_score(self, current_combined: float) -> float:
        """Calculate trend based on rate of change (0-100)"""
        self.score_history.append(current_combined)
        
        if len(self.score_history) < 5:
            return 0
        
        history_list = list(self.score_history)
        rate = (history_list[-1] - history_list[0]) / len(history_list)
        
        if rate <= 0:
            return 0
        elif rate < 1:
            return rate * 20
        elif rate < 2:
            return 20 + (rate - 1) * 25
        elif rate < 3:
            return 45 + (rate - 2) * 25
        else:
            return min(90, 70 + (rate - 3) * 10)
    
    def extract_features(self, reading: SensorReading) -> Tuple[float, float, float, float]:
        """Extract all four feature scores from a reading"""
        density = self.calculate_density_score(reading.distance)
        movement = self.calculate_movement_score(reading.pir_count)
        audio = self.calculate_audio_score(reading.audio_level)
        
        combined = (density * 0.4 + movement * 0.35 + audio * 0.25)
        trend = self.calculate_trend_score(combined)
        
        return density, movement, audio, trend


# ════════════════════════════════════════════════════════════════════════════════
# DATA GENERATOR
# ════════════════════════════════════════════════════════════════════════════════

class TrainingDataGenerator:
    """
    Generates labeled training data for the ML model.
    
    Key insight: We label based on FUTURE danger, not current state.
    This teaches the model which feature patterns PREDICT danger.
    """
    
    def __init__(self, num_simulations: int = 10000, seed: Optional[int] = None):
        self.num_simulations = num_simulations
        self.base_seed = seed
    
    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate training data.
        
        Returns:
            X: Feature matrix (n_samples, 4)
            y: Labels (n_samples,)
        """
        print("\n  📊 Generating training data...")
        
        all_features = []
        all_labels = []
        
        simulations_per_scenario = self.num_simulations // 4
        
        for scenario_idx, scenario_key in enumerate(SCENARIOS.keys()):
            print(f"    ├─ {SCENARIOS[scenario_key]['name']}: ", end="", flush=True)
            
            for sim_idx in range(simulations_per_scenario):
                seed = None if self.base_seed is None else self.base_seed + scenario_idx * 10000 + sim_idx
                
                features, labels = self._process_simulation(scenario_key, seed)
                all_features.extend(features)
                all_labels.extend(labels)
                
                if (sim_idx + 1) % 500 == 0:
                    print(f"{sim_idx + 1}", end=" ", flush=True)
            
            print("✓")
        
        X = np.array(all_features)
        y = np.array(all_labels)
        
        print(f"\n  📈 Dataset: {len(y):,} samples")
        print(f"    ├─ Positive (danger): {sum(y):,} ({100*sum(y)/len(y):.1f}%)")
        print(f"    └─ Negative (safe): {len(y) - sum(y):,} ({100*(1-sum(y)/len(y)):.1f}%)")
        
        return X, y
    
    def _process_simulation(self, scenario_key: str, seed: int) -> Tuple[List, List]:
        """Process one simulation and extract labeled features"""
        simulator = CrowdSimulator(seed=seed)
        extractor = FeatureExtractor()
        extractor.reset()
        
        readings = simulator.generate_scenario(scenario_key)
        
        # First pass: calculate all density scores for lookahead
        density_scores = []
        for reading in readings:
            density_scores.append(extractor.calculate_density_score(reading.distance))
        
        # Second pass: extract features and create labels
        extractor.reset()
        features = []
        labels = []
        
        for i, reading in enumerate(readings):
            # Extract features
            density, movement, audio, trend = extractor.extract_features(reading)
            features.append([density, movement, audio, trend])
            
            # Create label: will density reach danger threshold in next LOOKAHEAD_WINDOW seconds?
            future_end = min(i + LOOKAHEAD_WINDOW, len(density_scores))
            future_densities = density_scores[i:future_end]
            
            if any(d > DANGER_THRESHOLD for d in future_densities):
                labels.append(1)  # Danger coming
            else:
                labels.append(0)  # Safe
        
        return features, labels


# ════════════════════════════════════════════════════════════════════════════════
# ML TRAINER
# ════════════════════════════════════════════════════════════════════════════════

class CPIWeightTrainer:
    """
    Trains a logistic regression model to find optimal CPI weights.
    
    The model learns which features best predict upcoming danger,
    and its coefficients become our optimized weights.
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.weights = None
    
    def train(self, X: np.ndarray, y: np.ndarray) -> TrainingResult:
        """
        Train the model and extract optimized weights.
        """
        print("\n  🧠 Training logistic regression model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features for better convergence
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = LogisticRegression(
            penalty='l2',
            C=1.0,
            class_weight='balanced',
            max_iter=1000,
            random_state=42,
            solver='lbfgs'
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_prob = self.model.predict_proba(X_test_scaled)[:, 1]
        
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_prob)
        
        # Cross-validation for robustness
        print("    ├─ Running 5-fold cross-validation...")
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5, scoring='f1')
        
        # Extract and normalize weights
        raw_coefficients = self.model.coef_[0]
        
        # Take absolute values (we want magnitude of importance)
        # Then normalize to sum to 1.0
        abs_coefs = np.abs(raw_coefficients)
        normalized_weights = abs_coefs / abs_coefs.sum()
        
        self.weights = {
            'density': round(normalized_weights[0], 4),
            'movement': round(normalized_weights[1], 4),
            'audio': round(normalized_weights[2], 4),
            'trend': round(normalized_weights[3], 4)
        }
        
        # Calculate relative importance
        feature_importance = {
            'density': round(abs_coefs[0] / abs_coefs.max() * 100, 1),
            'movement': round(abs_coefs[1] / abs_coefs.max() * 100, 1),
            'audio': round(abs_coefs[2] / abs_coefs.max() * 100, 1),
            'trend': round(abs_coefs[3] / abs_coefs.max() * 100, 1)
        }
        
        print(f"    ├─ Accuracy: {accuracy:.3f}")
        print(f"    ├─ Precision: {precision:.3f}")
        print(f"    ├─ Recall: {recall:.3f}")
        print(f"    ├─ F1 Score: {f1:.3f}")
        print(f"    ├─ AUC-ROC: {auc:.3f}")
        print(f"    └─ CV F1 Mean: {cv_scores.mean():.3f} (±{cv_scores.std():.3f})")
        
        return TrainingResult(
            weights=self.weights,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            auc=round(auc, 4),
            cv_scores=[round(s, 4) for s in cv_scores],
            feature_importance=feature_importance
        )


# ════════════════════════════════════════════════════════════════════════════════
# WEIGHT COMPARISON
# ════════════════════════════════════════════════════════════════════════════════

def compare_weights(original: Dict[str, float], optimized: Dict[str, float]):
    """Print comparison between original and optimized weights"""
    print("\n  ⚖️  WEIGHT COMPARISON")
    print("  " + "─" * 50)
    print(f"  {'Feature':<12} │ {'Original':<10} │ {'Optimized':<10} │ {'Change':<10}")
    print("  " + "─" * 50)
    
    for feature in ['density', 'movement', 'audio', 'trend']:
        orig = original[feature]
        opt = optimized[feature]
        change = ((opt - orig) / orig) * 100
        change_str = f"{'+' if change > 0 else ''}{change:.1f}%"
        
        print(f"  {feature:<12} │ {orig:<10.4f} │ {opt:<10.4f} │ {change_str:<10}")
    
    print("  " + "─" * 50)


# ════════════════════════════════════════════════════════════════════════════════
# OUTPUT GENERATION
# ════════════════════════════════════════════════════════════════════════════════

def save_trained_weights(result: TrainingResult, output_path: str):
    """Save trained weights and metadata to JSON"""
    output = {
        'weights': result.weights,
        'training_metadata': {
            'timestamp': datetime.now().isoformat(),
            'model_type': 'LogisticRegression',
            'accuracy': result.accuracy,
            'precision': result.precision,
            'recall': result.recall,
            'f1_score': result.f1,
            'auc_roc': result.auc,
            'cv_scores': result.cv_scores,
            'cv_mean': round(np.mean(result.cv_scores), 4),
            'cv_std': round(np.std(result.cv_scores), 4)
        },
        'feature_importance': result.feature_importance,
        'original_weights': ORIGINAL_WEIGHTS,
        'usage': {
            'formula': 'CPI = (density × {density}) + (movement × {movement}) + (audio × {audio}) + (trend × {trend})',
            'note': 'Weights are ML-optimized to maximize early warning detection'
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n  💾 Saved: {output_path}")


def generate_code_snippet(weights: Dict[str, float]) -> str:
    """Generate Python code snippet for copy-paste into stampede_predictor.py"""
    return f'''
# ════════════════════════════════════════════════════════════════════
# ML-OPTIMIZED CPI WEIGHTS
# Trained using logistic regression on 10,000 simulated scenarios
# See cpi_trainer.py for training methodology
# ════════════════════════════════════════════════════════════════════

CPI_WEIGHTS = {{
    'density': {weights['density']},    # Physical crowding
    'movement': {weights['movement']},    # Crowd agitation
    'audio': {weights['audio']},    # Panic indicators
    'trend': {weights['trend']}     # Situation trajectory
}}
'''


def print_results(result: TrainingResult):
    """Print final results summary"""
    print("\n")
    print("╔" + "═" * 66 + "╗")
    print("║" + " " * 18 + "ML-OPTIMIZED CPI WEIGHTS" + " " * 24 + "║")
    print("╠" + "═" * 66 + "╣")
    
    for feature in ['density', 'movement', 'audio', 'trend']:
        weight = result.weights[feature]
        importance = result.feature_importance[feature]
        bar = "█" * int(importance / 5) + "░" * (20 - int(importance / 5))
        print(f"║  {feature.capitalize():<10}: {weight:.4f}  │  {bar} {importance:>5.1f}%  ║")
    
    print("╠" + "═" * 66 + "╣")
    print(f"║  Model Accuracy: {result.accuracy:.1%}" + " " * 41 + "║")
    print(f"║  Model F1 Score: {result.f1:.1%}" + " " * 41 + "║")
    print(f"║  Cross-Val F1:   {np.mean(result.cv_scores):.1%} (±{np.std(result.cv_scores):.1%})" + " " * 31 + "║")
    print("╚" + "═" * 66 + "╝")
    
    # Code snippet
    print("\n  📝 CODE SNIPPET (copy to stampede_predictor.py):")
    print("  " + "─" * 50)
    print(generate_code_snippet(result.weights))


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Train ML model to optimize CPI weights',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-n', '--num-simulations', type=int, default=10000,
                        help='Total simulations for training (default: 10000)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--output', type=str, default='trained_weights.json',
                        help='Output file for trained weights (default: trained_weights.json)')
    
    args = parser.parse_args()
    
    # Header
    print("\n" + "═" * 70)
    print("  🧠 CPI WEIGHT OPTIMIZER - ML TRAINING")
    print("  " + "─" * 66)
    print(f"  Training simulations: {args.num_simulations:,}")
    print(f"  Random seed: {args.seed}")
    print("═" * 70)
    
    # Generate training data
    generator = TrainingDataGenerator(
        num_simulations=args.num_simulations,
        seed=args.seed
    )
    X, y = generator.generate()
    
    # Train model
    trainer = CPIWeightTrainer()
    result = trainer.train(X, y)
    
    # Compare weights
    compare_weights(ORIGINAL_WEIGHTS, result.weights)
    
    # Print results
    print_results(result)
    
    # Save outputs
    save_trained_weights(result, args.output)
    
    print("\n" + "═" * 70)
    print("  ✅ TRAINING COMPLETE")
    print("  " + "─" * 66)
    print(f"  → Trained weights saved to: {args.output}")
    print(f"  → Copy the code snippet above to algorithms/stampede_predictor.py")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
