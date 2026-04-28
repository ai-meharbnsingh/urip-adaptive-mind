"""
Vendor questionnaire templates — P2B.7.3

These templates are used to send standardized questionnaires to vendors.
Storage/persistence is intentionally out of scope for this phase; this module
provides in-code templates that can later be moved to a DB table.
"""
from __future__ import annotations


def get_vendor_questionnaire_templates() -> dict:
    return {
        "SOC 2 Vendor Questionnaire": {
            "name": "SOC 2 Vendor Questionnaire",
            "questions": [
                {"id": "soc2_1", "text": "Do you maintain a SOC 2 report (Type I or Type II)?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_2", "text": "Is your SOC 2 report available under NDA on request?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_3", "text": "Do you enforce MFA for administrative access?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_4", "text": "Do you encrypt data at rest?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_5", "text": "Do you encrypt data in transit (TLS 1.2+)?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_6", "text": "Do you have a documented incident response plan?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_7", "text": "How frequently do you run vulnerability scans?", "answer_type": "text", "required": False},
                {"id": "soc2_8", "text": "Do you conduct annual penetration testing?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_9", "text": "Do you maintain an asset inventory for production systems?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_10", "text": "Do you perform background verification for employees with production access?", "answer_type": "yes_no", "required": False},
                {"id": "soc2_11", "text": "Rate your access review frequency (1=never, 5=quarterly or better).", "answer_type": "scale_1_5", "required": True},
                {"id": "soc2_12", "text": "Do you log and monitor privileged activity?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_13", "text": "Do you have a formal change management process?", "answer_type": "yes_no", "required": True},
                {"id": "soc2_14", "text": "Do you have a defined RTO/RPO for critical services?", "answer_type": "yes_no", "required": False},
                {"id": "soc2_15", "text": "Do you maintain backups and test restores at least annually?", "answer_type": "yes_no", "required": True},
            ],
        },
        "GDPR Data Processor Questionnaire": {
            "name": "GDPR Data Processor Questionnaire",
            "questions": [
                {"id": "gdpr_1", "text": "Do you act as a data processor under GDPR for our data?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_2", "text": "Do you have a DPA available for signature?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_3", "text": "Do you maintain a list of sub-processors and notify customers of changes?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_4", "text": "Do you support data subject requests (DSAR) within required timeframes?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_5", "text": "Do you have documented breach notification procedures?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_6", "text": "Do you provide breach notification within 72 hours of awareness?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_7", "text": "Do you perform privacy impact assessments for new processing activities?", "answer_type": "yes_no", "required": False},
                {"id": "gdpr_8", "text": "Where is data stored/processed (regions/countries)?", "answer_type": "text", "required": True},
                {"id": "gdpr_9", "text": "Do you support data deletion upon request?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_10", "text": "Do you apply encryption and access controls to personal data?", "answer_type": "yes_no", "required": True},
                {"id": "gdpr_11", "text": "Rate your logging/monitoring maturity (1=basic, 5=advanced).", "answer_type": "scale_1_5", "required": False},
                {"id": "gdpr_12", "text": "Do you provide audit support (e.g., SOC2/ISO certs) to customers?", "answer_type": "yes_no", "required": False},
            ],
        },
        "Security Baseline Questionnaire": {
            "name": "Security Baseline Questionnaire",
            "questions": [
                {"id": "sec_1", "text": "Do you require MFA for all user accounts?", "answer_type": "yes_no", "required": True},
                {"id": "sec_2", "text": "Do you require MFA for all administrator accounts?", "answer_type": "yes_no", "required": True},
                {"id": "sec_3", "text": "Do you use encryption in transit for all external connections?", "answer_type": "yes_no", "required": True},
                {"id": "sec_4", "text": "Do you use encryption at rest for customer data?", "answer_type": "yes_no", "required": True},
                {"id": "sec_5", "text": "Do you enforce least privilege and role-based access control?", "answer_type": "yes_no", "required": True},
                {"id": "sec_6", "text": "Do you have an incident response process and on-call coverage?", "answer_type": "yes_no", "required": True},
                {"id": "sec_7", "text": "Do you perform regular vulnerability scanning?", "answer_type": "yes_no", "required": True},
                {"id": "sec_8", "text": "Do you perform penetration testing at least annually?", "answer_type": "yes_no", "required": False},
                {"id": "sec_9", "text": "Rate your security training coverage (1=none, 5=all staff annually).", "answer_type": "scale_1_5", "required": False},
                {"id": "sec_10", "text": "Describe your approach to access reviews.", "answer_type": "text", "required": False},
            ],
        },
    }

