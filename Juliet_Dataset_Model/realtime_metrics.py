import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from feedback_system import FeedbackCollector

@dataclass
class RealtimeMetrics:
    overall_accuracy: float
    safe_accuracy: float
    vulnerable_accuracy: float
    precision: float
    recall: float
    f1_score: float
    false_positives: int
    false_negatives: int
    true_positives: int
    true_negatives: int
    total_feedback: int
    confidence_weighted_accuracy: float

class RealtimeMetricsCalculator:
    def __init__(self, feedback_collector: FeedbackCollector = None):
        self.feedback_collector = feedback_collector or FeedbackCollector()
        self.original_metrics = self._load_original_metrics()
    
    def _load_original_metrics(self) -> Dict:
        import json
        from pathlib import Path

        eval_file = Path("./Juliet_Dataset_Model/output/evaluation_results.json")

        try:
            with eval_file.open() as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading metrics from {eval_file}: {e}")
            return {}
        
    def calculate_realtime_metrics(self) -> RealtimeMetrics:

        feedback_entries = self.feedback_collector.get_all_feedback()

        false_positives, false_negatives = 0, 0 
        confidence_weighted_fp, confidence_weighted_fn = 0.0, 0.0
        
        for entry in feedback_entries:
            confidence = entry.confidence or 0.5
            if entry.feedback_type == "false_positive":
                false_positives += 1
                confidence_weighted_fp += confidence
            elif entry.feedback_type == "false_negative":
                false_negatives += 1
                confidence_weighted_fn += confidence
        
        orig = self.original_metrics
        total_safe = orig.get("total_safe", 65)
        total_vulnerable = orig.get("total_vulnerable", 64)
        total_samples = orig.get("total_samples", 129)

        original_tp = int(orig.get("vulnerable_accuracy", 0.8125) * total_vulnerable)
        original_tn = int(orig.get("safe_accuracy", 1.0) * total_safe)

        updated_tp = original_tp - false_negatives
        updated_tn = original_tn - false_positives
        updated_fp = false_positives
        updated_fn = false_negatives

        # Helper to avoid zero-division
        safe_div = lambda num, den: num / den if den else 0

        # Accuracies
        safe_accuracy = safe_div(updated_tn, total_safe)
        vulnerable_accuracy = safe_div(updated_tp, total_vulnerable)
        overall_accuracy = safe_div(updated_tp + updated_tn, total_samples)

        # Precision, recall, F1
        precision = safe_div(updated_tp, updated_tp + updated_fp)
        recall = safe_div(updated_tp, updated_tp + updated_fn)
        f1_score = safe_div(2 * precision * recall, precision + recall)

        # Confidence-weighted accuracy
        total_confidence_weight = confidence_weighted_fp + confidence_weighted_fn
        confidence_weighted_accuracy = (overall_accuracy - safe_div(total_confidence_weight, len(feedback_entries))
                                        if feedback_entries else overall_accuracy)

        return RealtimeMetrics(
            overall_accuracy=round(overall_accuracy, 4),
            safe_accuracy=round(safe_accuracy, 4),
            vulnerable_accuracy=round(vulnerable_accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1_score, 4),
            false_positives=false_positives,
            false_negatives=false_negatives,
            true_positives=updated_tp,
            true_negatives=updated_tn,
            total_feedback=len(feedback_entries),
            confidence_weighted_accuracy=round(confidence_weighted_accuracy, 4)
        )
    
    def print_realtime_metrics(self):
        metrics = self.calculate_realtime_metrics()
        comparison = self.get_metrics_comparison()
        
        print("REAL-TIME MODEL PERFORMANCE METRICS")
        print("=" * 50)
        
        print(f"\nCurrent Performance (with {metrics.total_feedback} feedback entries):")
        print(f"  Overall Accuracy: {metrics.overall_accuracy:.1%}")
        print(f"  Safe Code Accuracy: {metrics.safe_accuracy:.1%}")
        print(f"  Vulnerable Code Accuracy: {metrics.vulnerable_accuracy:.1%}")
        print(f"  Precision: {metrics.precision:.1%}")
        print(f"  Recall: {metrics.recall:.1%}")
        print(f"  F1-Score: {metrics.f1_score:.1%}")
        
        print(f"\nFeedback Impact:")
        print(f"  False Positives: {metrics.false_positives}")
        print(f"  False Negatives: {metrics.false_negatives}")
        print(f"  Confidence-Weighted Accuracy: {metrics.confidence_weighted_accuracy:.1%}")
        
    def export_realtime_metrics(self, output_file: str = "realtime_metrics.json"):
        metrics = self.calculate_realtime_metrics()
        
        export_data = {
            "timestamp": json.dumps({"$date": {"$numberLong": str(int(Path().cwd().stat().st_mtime * 1000))}}),
            "realtime_metrics": {
                "overall_accuracy": metrics.overall_accuracy,
                "safe_accuracy": metrics.safe_accuracy,
                "vulnerable_accuracy": metrics.vulnerable_accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "false_positives": metrics.false_positives,
                "false_negatives": metrics.false_negatives,
                "true_positives": metrics.true_positives,
                "true_negatives": metrics.true_negatives,
                "total_feedback": metrics.total_feedback,
                "confidence_weighted_accuracy": metrics.confidence_weighted_accuracy
            },
        }
        
        output_path = Path("feedback_data") / output_file
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Real-time metrics exported to: {output_path}")
        return output_path

def main():
    calculator = RealtimeMetricsCalculator()
    calculator.print_realtime_metrics()
    
    calculator.export_realtime_metrics()

if __name__ == "__main__":
    main()