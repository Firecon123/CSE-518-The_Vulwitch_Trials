#!/usr/bin/env python3
"""
Feedback Management Script

This script provides a command-line interface for managing user feedback
and retraining the vulnerability detection model.

Usage:
    python manage_feedback.py status          # Show feedback statistics
    python manage_feedback.py retrain         # Retrain model with feedback
    python manage_feedback.py export          # Export feedback data
    python manage_feedback.py clear           # Clear all feedback (with confirmation)
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from feedback_system import FeedbackCollector
from retrain_with_feedback import FeedbackRetrainer

def show_status():
    """Show current feedback status"""
    collector = FeedbackCollector()
    retrainer = FeedbackRetrainer()
    
    print("📊 FEEDBACK SYSTEM STATUS")
    print("="*50)
    
    # Show feedback stats
    stats = collector.get_feedback_stats()
    print(f"Total feedback entries: {stats['total_feedback']}")
    print(f"  - False positives: {stats['false_positives']}")
    print(f"  - False negatives: {stats['false_negatives']}")
    print(f"  - Corrections: {stats['corrections']}")
    print(f"Retrain count: {stats['retrain_count']}")
    
    if stats['last_retrain']:
        print(f"Last retrain: {stats['last_retrain']}")
    else:
        print("Last retrain: Never")
    
    print()
    
    # Show retrain readiness
    ready, message = retrainer.check_retrain_ready()
    print(f"Retrain ready: {'✅' if ready else '❌'} {message}")
    
    if ready:
        print("\n💡 You can retrain the model with: python manage_feedback.py retrain")

def retrain_model():
    """Retrain the model with accumulated feedback"""
    retrainer = FeedbackRetrainer()
    
    print("🔄 Starting model retraining with user feedback...")
    
    # Check if ready
    ready, message = retrainer.check_retrain_ready()
    if not ready:
        print(f"❌ {message}")
        return False
    
    print(f"✅ {message}")
    
    # Confirm retraining
    response = input("\nProceed with retraining? (y/N): ").strip().lower()
    if response != 'y':
        print("⏭️  Retraining cancelled")
        return False
    
    # Run retraining
    success = retrainer.full_retrain_pipeline()
    
    if success:
        print("🎉 Model retraining completed successfully!")
        print("The model has been improved with your feedback!")
    else:
        print("❌ Retraining failed. Check the logs above.")
    
    return success

def export_feedback():
    """Export feedback data for analysis"""
    collector = FeedbackCollector()
    
    print("📤 Exporting feedback data...")
    
    export_path = collector.export_feedback_for_analysis()
    print(f"✅ Feedback data exported to: {export_path}")
    
    # Show summary
    stats = collector.get_feedback_stats()
    print(f"\n📊 Exported data includes:")
    print(f"  - {stats['total_feedback']} feedback entries")
    print(f"  - {stats['false_positives']} false positives")
    print(f"  - {stats['false_negatives']} false negatives")
    print(f"  - {stats['corrections']} corrections")

def clear_feedback():
    """Clear all feedback data (with confirmation)"""
    collector = FeedbackCollector()
    
    stats = collector.get_feedback_stats()
    
    if stats['total_feedback'] == 0:
        print("📭 No feedback data to clear")
        return
    
    print("⚠️  WARNING: This will permanently delete all feedback data!")
    print(f"   - {stats['total_feedback']} feedback entries")
    print(f"   - {stats['false_positives']} false positives")
    print(f"   - {stats['false_negatives']} false negatives")
    print(f"   - {stats['corrections']} corrections")
    
    response = input("\nAre you sure you want to clear all feedback? (yes/NO): ").strip().lower()
    if response != 'yes':
        print("⏭️  Clear operation cancelled")
        return
    
    # Clear feedback files
    feedback_dir = Path("feedback_data")
    if feedback_dir.exists():
        import shutil
        shutil.rmtree(feedback_dir)
        print("✅ All feedback data cleared")
    else:
        print("📭 No feedback data found to clear")

def show_recent_feedback():
    """Show recent feedback entries"""
    collector = FeedbackCollector()
    
    all_feedback = collector.get_all_feedback()
    
    if not all_feedback:
        print("📭 No feedback entries found")
        return
    
    print("📝 RECENT FEEDBACK ENTRIES")
    print("="*60)
    
    # Show last 10 entries
    recent_feedback = all_feedback[-10:]
    
    for i, entry in enumerate(recent_feedback, 1):
        print(f"\n{i}. ID: {entry.id}")
        print(f"   Type: {entry.feedback_type}")
        print(f"   Original: {entry.original_prediction}")
        print(f"   Correction: {entry.user_correction}")
        print(f"   Time: {entry.timestamp}")
        if entry.user_notes:
            print(f"   Notes: {entry.user_notes}")

def main():
    """Main command line interface"""
    parser = argparse.ArgumentParser(
        description="Manage user feedback and model retraining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_feedback.py status          # Show feedback statistics
  python manage_feedback.py retrain         # Retrain model with feedback
  python manage_feedback.py export          # Export feedback data
  python manage_feedback.py recent          # Show recent feedback
  python manage_feedback.py clear           # Clear all feedback
        """
    )
    
    parser.add_argument("command", 
                       choices=["status", "retrain", "export", "recent", "clear"],
                       help="Command to execute")
    
    args = parser.parse_args()
    
    try:
        if args.command == "status":
            show_status()
        elif args.command == "retrain":
            retrain_model()
        elif args.command == "export":
            export_feedback()
        elif args.command == "recent":
            show_recent_feedback()
        elif args.command == "clear":
            clear_feedback()
    
    except KeyboardInterrupt:
        print("\n⏭️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
