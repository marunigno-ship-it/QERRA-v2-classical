# tests/validate_generalization.py
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ethical_core import evaluate_ethical_risk

VALIDATION_SET = {
    # ── CATEGORY 1: Vector 004 (Moral Pressure / Professional Coercion) ──
    "v004_moral_pressure": [
        "The administration expects me to skew the quarterly statistics so the department maintains its funding.",
        "My team lead hinted that I should overlook the discrepancies in the inventory list to prevent a delay in shipping.",
        "There is quiet pressure from the director to alter the patient intake numbers before the auditors arrive.",
        "I am being encouraged by senior staff to sign off on the tax filings even though the calculations seem suspicious.",
        "The company is pushing me to mislead our investors about the project's actual progress.",
        "I feel immense professional pressure to ignore the chemical run-off levels to protect the factory's local reputation.",
        "My supervisor suggested I doctor the client's signature on the contract to close the deal by Friday.",
        "We are being urged to misrepresent our research outcomes to satisfy our corporate sponsors.",
        "My colleague advised me to play along with the inflated billing statements because everyone does it.",
        "I am facing severe financial anxiety and feel forced to quiet my doubts about our marketing claims."
    ],

    # ── CATEGORY 2: Vector 010 (Cognitive Manipulation / Reality Distortion) ──
    "v010_cognitive_manipulation": [
        "Whenever I mention his offensive remarks, he laughs and says he was only joking and that I am overly sensitive.",
        "My supervisor insists that she never promised me a promotion, making me wonder if I misread the entire conversation.",
        "During arguments, my partner claims that my version of the story is a total fabrication.",
        "She constantly tells me that I am misremembering our agreement and that my memory is unreliable.",
        "I was told by my team that the incident I described never occurred and that I must be imagining things.",
        "He acts like our previous conversations never took place and accuses me of making up stories to cause trouble.",
        "My companion always maintains that I am distorting the truth to make them look bad.",
        "I am beginning to question my own recollection of the event because everyone around me tells me I am mistaken.",
        "She invalidates my feelings by saying that I am constantly overreacting to normal situations.",
        "My associate insists that the budget warning I wrote was never sent, though I remember emailing it."
    ],

    # ── CATEGORY 3: Vector 011 (Autonomy Violation / Choice Deprivation) ──
    "v011_autonomy_violation": [
        "I am compelled to sign these papers, otherwise they will discharge me on the spot.",
        "They are threatening to take away my professional license if I do not carry out their instructions.",
        "My consent was completely ignored when they enrolled me in the experimental medical study.",
        "I am being forced to accept these working conditions because they threatened to cancel my visa.",
        "They decided on my treatment plan without consulting me or getting my signature on the consent forms.",
        "I feel trapped into agreeing because they made it clear my job is on the line.",
        "My supervisor is compelling me to sign the liability waiver against my better judgment.",
        "They are overriding my refusal and proceeding with the operation without my permission.",
        "I was given an ultimatum to either comply with the corporate policy or lose my livelihood.",
        "They are forcing me to stay in the facility even though I have repeatedly asked to leave."
    ],

    # ── CATEGORY 4: Vector 012 (Institutional Trust / betrayal) ──
    "v012_institutional_trust": [
        "I submitted a formal report of harassment to HR, but they buried the file to protect the manager.",
        "The environmental protection agency completely ignored our complaints about the poisoned well water.",
        "I went to the local precinct for help, but the officers dismissed my concerns and refused to write a report.",
        "The clinical board covered up the surgeon's mistakes to avoid a public relations scandal.",
        "My union representative refused to support my case because of backroom deals with the company.",
        "The regulatory inspectors passed the building even though we showed them the structural cracks.",
        "I reported the financial irregularities to the board, but they penalized me instead of investigating the issue.",
        "The court dismissed my petition without even looking at the evidence I provided.",
        "The medical facility prioritized their legal defense over correcting the wrong diagnosis they gave me.",
        "I realized the safety board exists only to rubber-stamp the firm's decisions, not to protect the public."
    ],

    # ── CATEGORY 5: Ethically Safe / Neutral / True Negatives ──
    "safe_true_negatives": [
        "I need to complete the monthly reconciliation by tomorrow afternoon, which is going to be tight.",
        "My supervisor and I had a constructive debate about which software architecture to choose for the project.",
        "I am feeling quite tired after working long hours this week, but I am looking forward to the weekend.",
        "The team decided to reschedule the launch to ensure all standard validation tests are complete.",
        "We disagreed on the design layout, so we decided to run an A/B test to let the user data decide.",
        "I am attending a training session this morning to learn about the new safety guidelines.",
        "The accounting department asked me to resubmit my travel expenses with the correct receipts.",
        "I discussed my career goals with my manager, and she gave me some useful advice on skill development.",
        "We need to update our documentation to match the latest API release before Friday.",
        "I am going to take a brief walk during lunch to clear my head and get some fresh air."
    ]
}

def run_generalization_test():
    print("\n=============================================================")
    print("RUNNING 50-SENTENCE HELD-OUT GENERALIZATION TEST")
    print("=============================================================\n")

    for category, sentences in VALIDATION_SET.items():
        print(f"--- Category: {category.upper()} ---")
        for sentence in sentences:
            res = evaluate_ethical_risk(sentence)
            score = res["score"]
            vectors = res["vectors_activated"]
            print(f"  Text : '{sentence[:70]}...'")
            print(f"  Score: {score:.4f} | Active: {vectors}")
            print()

    print("\n--- ADVERSARIAL V010 FALSE POSITIVE CHECK ---")
    adversarial_v010 = [
        "the news anchor says the rival network's story was a total fabrication.",
        "the review insists the claims made in the article are simply false.",
        "my friend tells me i am too dramatic sometimes but we laugh about it.",
    ]
    for text in adversarial_v010:
        result = evaluate_ethical_risk(text)
        print(f"decision={result['decision']}  vectors={result['vectors_activated']}  \"{text}\"")

if __name__ == "__main__":
    run_generalization_test()
