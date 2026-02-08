#!/usr/bin/env python3
"""Prepare training dataset for fine-tuning.

Generates instruction-output pairs from document samples.
"""

import json
import argparse
from pathlib import Path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Prepare training dataset")

    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/raw",
        help="Directory with raw documents",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="data/training/legal_summaries.json",
        help="Output training data file",
    )
    parser.add_argument(
        "--task",
        type=str,
        choices=["summarize", "qa", "compliance", "all"],
        default="all",
        help="Task type to generate data for",
    )

    return parser.parse_args()


# Sample training data templates
SAMPLE_DATA = [
    # Summarization examples
    {
        "instruction": "Provide a concise executive summary of this legal contract.",
        "input": """SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 1, 2026,
by and between TechCorp Inc. ("Provider") and ClientCo LLC ("Client").

1. SERVICES: Provider shall provide software development and maintenance 
services as described in Exhibit A.

2. TERM: The initial term is 12 months, automatically renewing unless 
terminated with 30 days notice.

3. COMPENSATION: Client shall pay $25,000 monthly, due within 30 days of invoice.

4. CONFIDENTIALITY: Both parties agree to protect proprietary information.

5. LIMITATION OF LIABILITY: Neither party liable for indirect damages; 
total liability capped at fees paid in prior 12 months.

6. TERMINATION: Either party may terminate for material breach with 30 days 
written notice and opportunity to cure.""",
        "output": """This Service Agreement establishes a 12-month software development engagement between TechCorp Inc. (Provider) and ClientCo LLC (Client), effective January 1, 2026.

Key Terms:
- Monthly fee: $25,000
- Auto-renewal with 30-day termination notice
- Standard confidentiality protections
- Liability capped at 12 months of fees
- 30-day cure period for breach termination

The agreement includes typical protective clauses and a balanced risk allocation appropriate for enterprise software services.""",
    },
    # QA examples
    {
        "instruction": "Answer this question about the contract: What is the payment term?",
        "input": """CONSULTING AGREEMENT

Payment Terms: Consultant shall invoice Client monthly. Payment is due 
within 45 days of invoice receipt. Late payments accrue interest at 1.5% 
per month. Client may dispute invoices within 15 days of receipt.""",
        "output": """Based on the contract, the payment terms are:
- Payment due within 45 days of invoice receipt
- Late payments incur 1.5% monthly interest
- Clients have 15 days to dispute invoices

[Source: Payment Terms section]""",
    },
    # Compliance examples
    {
        "instruction": "Identify any GDPR compliance concerns in this data processing clause.",
        "input": """DATA PROCESSING

Provider may process Client data for service delivery purposes. Data may be 
transferred to Provider's global data centers. Client warrants it has obtained 
necessary consents for personal data. Provider implements industry-standard 
security measures. Data retained for contract duration plus 7 years.""",
        "output": """GDPR Compliance Analysis:

Issues Identified:
1. [MEDIUM] International transfer clause lacks specific safeguards (SCCs, BCRs, or adequacy decisions)
2. [LOW] Vague "industry-standard security" - GDPR requires specific technical measures
3. [HIGH] 7-year retention may exceed data minimization requirements without justification
4. [MEDIUM] No mention of data subject rights (access, deletion, portability)

Recommendations:
- Add Standard Contractual Clauses for international transfers
- Specify security measures (encryption, access controls)
- Include data subject rights procedures
- Justify 7-year retention with legal basis

Overall Risk: MEDIUM (requires DPO review before signing)""",
    },
    # Complex summarization
    {
        "instruction": "Create a structured summary of this employment contract identifying key obligations for both parties.",
        "input": """EMPLOYMENT AGREEMENT

EMPLOYER: GlobalTech Corporation
EMPLOYEE: Jane Smith
POSITION: Senior Software Engineer
START DATE: February 1, 2026

COMPENSATION: Base salary of $180,000 annually, paid bi-weekly. Eligible 
for annual bonus up to 20% based on performance. Stock options per 
separate Stock Option Agreement.

DUTIES: Employee shall perform software development duties, report to 
Engineering Manager, and comply with company policies.

CONFIDENTIALITY: Employee agrees to protect company confidential 
information during and after employment.

NON-COMPETE: For 12 months post-employment, Employee shall not work for 
direct competitors within 50 miles of any company office.

TERMINATION: Either party may terminate with 2 weeks notice. Employer 
may terminate immediately for cause. Severance of 3 months salary if 
terminated without cause after 1 year of service.

INTELLECTUAL PROPERTY: All work product created during employment 
belongs to Employer.""",
        "output": """# Employment Agreement Summary

## Parties
- **Employer**: GlobalTech Corporation
- **Employee**: Jane Smith (Senior Software Engineer)
- **Start Date**: February 1, 2026

## Employer Obligations
| Obligation | Details |
|------------|---------|
| Base Compensation | $180,000/year, bi-weekly payments |
| Bonus | Up to 20% annual (performance-based) |
| Equity | Stock options (separate agreement) |
| Severance | 3 months salary if terminated without cause (after 1 year) |
| Notice | 2 weeks for termination |

## Employee Obligations
| Obligation | Details |
|------------|---------|
| Role | Software development, report to Engineering Manager |
| Confidentiality | Ongoing (during and after employment) |
| Non-Compete | 12 months, 50-mile radius from offices |
| IP Assignment | All work product belongs to employer |
| Notice | 2 weeks for resignation |

## Risk Assessment
- **Non-compete**: Standard but enforceable depending on state law
- **IP clause**: Broad - covers all work during employment
- **Severance**: Only after 1 year tenure""",
    },
]


def generate_training_data(task: str = "all") -> list[dict]:
    """Generate training data for specified task."""
    if task == "all":
        return SAMPLE_DATA

    task_keywords = {
        "summarize": ["summary", "summarize", "key terms"],
        "qa": ["answer", "question"],
        "compliance": ["compliance", "GDPR", "risk"],
    }

    keywords = task_keywords.get(task, [])
    return [
        d for d in SAMPLE_DATA if any(kw.lower() in d["instruction"].lower() for kw in keywords)
    ]


def main():
    """Main function."""
    args = parse_args()

    # Create output directory
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate data
    data = generate_training_data(args.task)

    print(f"Generated {len(data)} training examples for task: {args.task}")

    # Save to file
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
