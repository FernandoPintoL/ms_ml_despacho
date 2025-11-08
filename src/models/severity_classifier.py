"""
Severity Classifier Model
Classifies medical case urgency into 5 levels (Critical to Information)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
import re

from .base_model import BaseModel


class SeverityClassifier(BaseModel):
    """
    Classifies medical cases by urgency level

    Levels:
    1 = Critical (Cardiac arrest, severe bleeding, etc)
    2 = High (Chest pain, difficulty breathing, etc)
    3 = Medium (Moderate pain, fever, etc)
    4 = Low (Minor injury, mild pain, etc)
    5 = Information (Non-emergency call)

    Features:
    - Patient description/symptoms
    - Vital signs (if available)
    - Age (if available)
    - Keywords in description
    """

    # Keywords mapping for severity levels
    CRITICAL_KEYWORDS = {
        'cardiac', 'arrest', 'severe', 'bleeding', 'unconscious',
        'unresponsive', 'shock', 'severe trauma', 'respiratory arrest',
        'myocardial infarction', 'stroke', 'sepsis'
    }

    HIGH_KEYWORDS = {
        'chest pain', 'difficulty breathing', 'dyspnea', 'acute',
        'severe pain', 'trauma', 'head injury', 'poison', 'overdose',
        'seizure', 'syncope', 'severe allergy', 'anaphylaxis'
    }

    MEDIUM_KEYWORDS = {
        'pain', 'fever', 'nausea', 'vomiting', 'dizziness', 'weakness',
        'injury', 'burn', 'fracture', 'sprain', 'laceration',
        'moderate fever', 'abdominal pain'
    }

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize Severity Classifier

        Args:
            model_path: Path to pre-trained model
        """
        self.tfidf = None
        self.vital_scaler = None
        super().__init__(
            model_name='severity',
            model_type='naive_bayes',
            model_path=model_path,
            version='1.0.0'
        )

    def _initialize_model(self):
        """Initialize untrained model"""
        self.model = MultinomialNB(alpha=0.1)
        self.tfidf = TfidfVectorizer(
            max_features=100,
            ngram_range=(1, 2),
            lowercase=True,
            stop_words='english'
        )
        self.vital_scaler = StandardScaler()
        self.feature_names = ['description', 'heart_rate', 'blood_pressure', 'temperature']
        self.log_info("Initialized Naive Bayes Severity Classifier")

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs
    ) -> Dict[str, float]:
        """
        Train the severity classifier

        Args:
            X_train: Training features (descriptions or mixed data)
            y_train: Training labels (severity levels 1-5)
            X_val: Validation features
            y_val: Validation labels
            **kwargs: Additional parameters

        Returns:
            Training metrics
        """
        try:
            self.log_info(f"Starting Severity Classifier training with {len(X_train)} samples")

            # Handle different input formats
            if isinstance(X_train, np.ndarray):
                if len(X_train.shape) == 1:
                    # Array of strings
                    descriptions = X_train
                else:
                    # Multiple features
                    descriptions = X_train[:, 0] if X_train.shape[1] > 0 else X_train

            # Fit TF-IDF vectorizer and transform
            X_tfidf = self.tfidf.fit_transform(descriptions)

            # Train model
            self.model.fit(X_tfidf, y_train)

            # Evaluate on training data
            y_pred = self.model.predict(X_tfidf)
            accuracy = np.mean(y_pred == y_train)

            metrics = {
                'accuracy': float(accuracy),
                'samples': len(y_train),
                'classes': len(np.unique(y_train))
            }

            # Evaluate on validation set if provided
            if X_val is not None and y_val is not None:
                X_val_tfidf = self.tfidf.transform(X_val)
                y_val_pred = self.model.predict(X_val_tfidf)
                val_accuracy = np.mean(y_val_pred == y_val)
                metrics['validation_accuracy'] = float(val_accuracy)

            self.metadata['trained_at'] = pd.Timestamp.now().isoformat()
            self.metadata['training_samples'] = len(y_train)

            self.log_info(f"Severity Classifier training completed: {metrics}")
            return metrics

        except Exception as e:
            self.log_error(f"Error training Severity Classifier: {str(e)}")
            raise

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict severity level

        Args:
            features: Dictionary with:
                - description (str): Patient description/symptoms
                - heart_rate (int, optional): Beats per minute
                - blood_pressure (str, optional): Systolic/Diastolic
                - temperature (float, optional): Celsius
                - age (int, optional): Patient age

        Returns:
            Dictionary with:
                - level: Severity level (1-5)
                - category: Level name (Critical, High, Medium, Low, Info)
                - confidence: Confidence score (0-1)
                - keywords_found: List of severity keywords found
                - recommendation: Clinical recommendation
        """
        try:
            description = features.get('description', '').lower()

            if not description:
                return self._create_prediction(5, 'Information', 0.5, [], 'Call back with more information')

            # Get keywords found
            keywords_found = self._extract_keywords(description)

            # Keyword-based urgency scoring
            keyword_level = self._score_by_keywords(keywords_found)

            # Vital signs analysis
            vital_level = self._score_by_vitals(features)

            # Combine scores
            combined_level = max(keyword_level, vital_level)
            combined_level = min(5, max(1, combined_level))  # Clamp to 1-5

            # TF-IDF prediction if model is trained
            if self.tfidf.get_feature_names_out().__len__() > 0:
                X_tfidf = self.tfidf.transform([description])
                tfidf_proba = self.model.predict_proba(X_tfidf)[0]
                tfidf_level = np.argmax(tfidf_proba) + 1  # Assume 0-4 classes map to 1-5
                confidence = float(np.max(tfidf_proba))
            else:
                tfidf_level = combined_level
                confidence = 0.7

            # Final level is average of methods
            final_level = int(np.round((combined_level + tfidf_level) / 2))
            final_level = min(5, max(1, final_level))

            # Get category name
            category = self._get_category(final_level)
            recommendation = self._get_recommendation(final_level)

            result = self._create_prediction(
                final_level,
                category,
                confidence,
                list(keywords_found),
                recommendation
            )

            self.log_debug(f"Severity prediction: {result}")
            return result

        except Exception as e:
            self.log_error(f"Error predicting severity: {str(e)}")
            raise

    def predict_batch(self, features_list: list) -> list:
        """
        Batch predict severity for multiple cases

        Args:
            features_list: List of feature dictionaries

        Returns:
            List of predictions
        """
        predictions = []
        for features in features_list:
            pred = self.predict(features)
            predictions.append(pred)
        return predictions

    def _extract_keywords(self, description: str) -> set:
        """Extract relevant keywords from description"""
        words = set(description.lower().split())
        keywords = set()

        for keyword in self.CRITICAL_KEYWORDS | self.HIGH_KEYWORDS | self.MEDIUM_KEYWORDS:
            if keyword in description.lower():
                keywords.add(keyword)

        return keywords

    def _score_by_keywords(self, keywords: set) -> int:
        """Score urgency based on keywords found"""
        if any(kw in keywords for kw in self.CRITICAL_KEYWORDS):
            return 1
        elif any(kw in keywords for kw in self.HIGH_KEYWORDS):
            return 2
        elif any(kw in keywords for kw in self.MEDIUM_KEYWORDS):
            return 3
        else:
            return 4

    def _score_by_vitals(self, features: Dict[str, Any]) -> int:
        """Score urgency based on vital signs"""
        score = 4  # Default to Low

        # Check heart rate
        hr = features.get('heart_rate')
        if hr:
            if hr < 40 or hr > 120:
                score = min(score, 2)  # High
            elif hr < 50 or hr > 100:
                score = min(score, 3)  # Medium

        # Check blood pressure
        bp = features.get('blood_pressure', '')
        if bp:
            try:
                systolic = int(bp.split('/')[0])
                if systolic < 90 or systolic > 180:
                    score = min(score, 2)  # High
                elif systolic < 100 or systolic > 160:
                    score = min(score, 3)  # Medium
            except:
                pass

        # Check temperature
        temp = features.get('temperature')
        if temp:
            if temp > 39.5 or temp < 35:
                score = min(score, 2)  # High
            elif temp > 39 or temp < 36:
                score = min(score, 3)  # Medium

        return score

    def _get_category(self, level: int) -> str:
        """Get category name for level"""
        categories = {
            1: 'Critical',
            2: 'High',
            3: 'Medium',
            4: 'Low',
            5: 'Information'
        }
        return categories.get(level, 'Unknown')

    def _get_recommendation(self, level: int) -> str:
        """Get clinical recommendation"""
        recommendations = {
            1: 'IMMEDIATE response required - Dispatch ambulance NOW',
            2: 'Urgent response needed - Dispatch ambulance with priority',
            3: 'Standard response - Dispatch ambulance',
            4: 'Non-emergency - Consider alternative transport',
            5: 'Information call - No emergency response needed'
        }
        return recommendations.get(level, 'Dispatch ambulance')

    def _create_prediction(
        self,
        level: int,
        category: str,
        confidence: float,
        keywords: list,
        recommendation: str
    ) -> Dict[str, Any]:
        """Create prediction result dictionary"""
        return {
            'level': level,
            'category': category,
            'confidence': round(confidence, 2),
            'keywords_found': keywords,
            'recommendation': recommendation,
            'severity_score': level * 20  # 20-100 scale for UI
        }
