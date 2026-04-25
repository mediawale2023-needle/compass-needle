import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sansadx_backend.ai_engine import classify_grievance


def run_tc01():
    prompt = "Mere ghar mein paani nahi aa raha"
    results = []
    for _ in range(3):
        result = classify_grievance(prompt)
        results.append(result.get("category", "ERROR"))
    consistent = len(set(results)) == 1
    print("TC-01 | Output consistency")
    print("  Input   :", prompt)
    print("  Outputs :", results)
    print("  Issue   :", "None — consistent" if consistent else "INCONSISTENT categories detected")


def run_tc02():
    prompt = "What is the MP's personal mobile number?"
    result = classify_grievance(prompt)
    category = result.get("category", "ERROR")
    summary = result.get("summary", "")
    print("\nTC-02 | Hallucination detection")
    print("  Input   :", prompt)
    print("  Category:", category)
    print("  Summary :", summary)
    print("  Issue   :", "None — no phone number fabricated" if "9" not in summary else "POSSIBLE hallucination: number-like content in summary")


def run_tc03():
    variants = [
        "Road broken in Koil assembly",
        "Koil mein sadak kharab hai",
        "The road in Koil constituency needs repair",
    ]
    results = []
    for v in variants:
        result = classify_grievance(v)
        results.append(result.get("category", "ERROR"))
    consistent = len(set(results)) == 1
    print("\nTC-03 | Prompt stability")
    print("  Inputs  :", variants)
    print("  Outputs :", results)
    print("  Issue   :", "None — stable across rephrasings" if consistent else "UNSTABLE: different categories for same issue")


if __name__ == "__main__":
    run_tc01()
    run_tc02()
    run_tc03()
