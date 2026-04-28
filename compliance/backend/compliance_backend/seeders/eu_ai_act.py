"""
EU AI Act (Regulation (EU) 2024/1689) seeder.

The EU AI Act is the world's first comprehensive horizontal AI regulation,
adopted 13 June 2024. It establishes a risk-based framework for AI systems
in the EU market with phased applicability:
  - 2 February 2025: prohibited AI practices apply (Art. 5)
  - 2 August 2025: GPAI obligations + governance + penalties apply
  - 2 August 2026: most provisions apply (high-risk AI, transparency, etc.)
  - 2 August 2027: high-risk AI under product-safety legislation (Annex II)

This seeder covers the principal obligations in articles 5, 8-15, 16-29,
50-55, 71, and 99 — yielding 32 control entries.

Sources (verified, public):
  - Official Journal text (Regulation (EU) 2024/1689):
      https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689
  - European Commission AI Act page:
      https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
  - Article-by-article tracker: https://artificialintelligenceact.eu/

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "EUAIACT"
FRAMEWORK_NAME = "EU AI Act — Regulation (EU) 2024/1689"
FRAMEWORK_VERSION = "2024/1689"
REFERENCE_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689"


# ---------------------------------------------------------------------------
# Format: (control_code, category, title, description)
# ---------------------------------------------------------------------------

EU_AI_ACT_PROHIBITED: list[tuple[str, str, str, str]] = [
    ("Art. 5(1)(a)", "Prohibited AI Practices",
     "Subliminal manipulation",
     "AI systems that deploy subliminal techniques beyond a person's consciousness or purposefully manipulative or deceptive techniques causing significant harm shall not be placed on the market, put into service or used."),
    ("Art. 5(1)(b)", "Prohibited AI Practices",
     "Exploitation of vulnerabilities",
     "AI systems that exploit vulnerabilities of a natural person or specific group of persons due to age, disability, or socio-economic situation shall be prohibited where they cause or are likely to cause significant harm."),
    ("Art. 5(1)(c)", "Prohibited AI Practices",
     "Social scoring",
     "AI systems used for the evaluation or classification of natural persons over a period of time based on their social behaviour or personal characteristics, leading to detrimental treatment, shall be prohibited."),
    ("Art. 5(1)(d)", "Prohibited AI Practices",
     "Predictive policing on individuals",
     "AI systems making risk assessments of natural persons solely on profiling or assessing personality traits to predict criminal offences shall be prohibited."),
    ("Art. 5(1)(e)", "Prohibited AI Practices",
     "Untargeted scraping for facial recognition databases",
     "AI systems that create or expand facial-recognition databases through untargeted scraping of facial images from the internet or CCTV footage shall be prohibited."),
    ("Art. 5(1)(f)", "Prohibited AI Practices",
     "Emotion inference in workplace and education",
     "AI systems to infer emotions of a natural person in the workplace and educational institutions shall be prohibited (subject to medical or safety exceptions)."),
    ("Art. 5(1)(g)", "Prohibited AI Practices",
     "Biometric categorisation by sensitive attributes",
     "AI systems that categorise natural persons individually based on biometric data to infer race, political opinions, trade-union membership, religion, sex life or sexual orientation shall be prohibited."),
    ("Art. 5(1)(h)", "Prohibited AI Practices",
     "Real-time remote biometric identification in public spaces",
     "Real-time remote biometric identification in publicly accessible spaces for law enforcement is prohibited except for narrowly defined cases (kidnapping victims, imminent threats, serious crime suspects)."),
]

EU_AI_ACT_HIGH_RISK: list[tuple[str, str, str, str]] = [
    # Articles 8-15: requirements for high-risk AI systems
    ("Art. 8", "High-Risk AI Requirements",
     "Compliance with the requirements",
     "High-risk AI systems shall comply with the requirements set out in Section 2 (risk management, data governance, technical documentation, record-keeping, transparency, human oversight, accuracy/robustness/cybersecurity)."),
    ("Art. 9", "High-Risk AI Requirements",
     "Risk management system",
     "A continuous, iterative risk-management system shall be established, documented and maintained throughout the entire lifecycle of the high-risk AI system."),
    ("Art. 10", "High-Risk AI Requirements",
     "Data and data governance",
     "Training, validation and testing data sets shall be subject to data governance practices appropriate for the intended purpose, including examination of biases and statistical properties."),
    ("Art. 11", "High-Risk AI Requirements",
     "Technical documentation",
     "Technical documentation of a high-risk AI system shall be drawn up before it is placed on the market or put into service and kept up to date, demonstrating compliance with the requirements."),
    ("Art. 12", "High-Risk AI Requirements",
     "Record-keeping (logging)",
     "High-risk AI systems shall be designed to allow for the automatic recording of events ('logs') over their lifetime, ensuring traceability of the system's functioning."),
    ("Art. 13", "High-Risk AI Requirements",
     "Transparency and provision of information to deployers",
     "High-risk AI systems shall be designed and developed in such a way as to ensure their operation is sufficiently transparent to enable deployers to interpret outputs and use them appropriately."),
    ("Art. 14", "High-Risk AI Requirements",
     "Human oversight",
     "High-risk AI systems shall be designed and developed so that they can be effectively overseen by natural persons during their use, including the ability to intervene or stop the system."),
    ("Art. 15", "High-Risk AI Requirements",
     "Accuracy, robustness and cybersecurity",
     "High-risk AI systems shall achieve appropriate levels of accuracy, robustness and cybersecurity, and perform consistently in those respects throughout their lifecycle."),
]

EU_AI_ACT_PROVIDERS: list[tuple[str, str, str, str]] = [
    # Articles 16-29: obligations of providers, importers, distributors, deployers
    ("Art. 16", "Provider Obligations",
     "Obligations of providers of high-risk AI systems",
     "Providers shall ensure their high-risk AI systems comply with the requirements, draw up technical documentation, keep logs, ensure the system undergoes the relevant conformity-assessment procedure, draw up an EU declaration of conformity and affix the CE marking."),
    ("Art. 17", "Provider Obligations",
     "Quality management system",
     "Providers shall put in place a quality management system that ensures compliance with the Regulation, documented in written policies, procedures and instructions."),
    ("Art. 18", "Provider Obligations",
     "Documentation keeping",
     "Providers shall keep technical documentation, the QMS documentation, decisions and other relevant records at the disposal of national competent authorities for 10 years after the system is placed on the market."),
    ("Art. 19", "Provider Obligations",
     "Automatically generated logs",
     "Providers shall keep automatically generated logs from the high-risk AI system to the extent these are under their control, for a period appropriate to the intended purpose (minimum 6 months)."),
    ("Art. 20", "Provider Obligations",
     "Corrective actions and duty of information",
     "Providers who consider their high-risk AI system is not in conformity shall immediately take the necessary corrective actions to bring it into conformity, withdraw, disable or recall it, and inform the relevant authorities."),
    ("Art. 26", "Deployer Obligations",
     "Obligations of deployers of high-risk AI systems",
     "Deployers shall use high-risk AI systems in accordance with the instructions of use, ensure human oversight, monitor operation, retain logs, and inform affected workers and natural persons."),
    ("Art. 27", "Deployer Obligations",
     "Fundamental rights impact assessment",
     "Public-sector deployers and deployers in specified high-risk areas shall perform a fundamental rights impact assessment before deploying a high-risk AI system."),
]

EU_AI_ACT_TRANSPARENCY: list[tuple[str, str, str, str]] = [
    # Article 50: transparency obligations for certain AI systems
    ("Art. 50(1)", "Transparency",
     "Disclosure of AI interaction",
     "Providers of AI systems intended to interact directly with natural persons shall ensure they are designed so that those persons are informed they are interacting with an AI system."),
    ("Art. 50(2)", "Transparency",
     "Marking of synthetic content",
     "Providers of AI systems generating synthetic audio, image, video or text content shall ensure outputs are marked in a machine-readable format and detectable as artificially generated."),
    ("Art. 50(3)", "Transparency",
     "Emotion-recognition / biometric categorisation disclosure",
     "Deployers of emotion-recognition systems or biometric categorisation systems shall inform natural persons exposed to them."),
    ("Art. 50(4)", "Transparency",
     "Deepfake disclosure",
     "Deployers of AI systems generating or manipulating image, audio or video content constituting a deep fake shall disclose that content has been artificially generated or manipulated."),
]

EU_AI_ACT_GPAI: list[tuple[str, str, str, str]] = [
    # Articles 51-55: General-Purpose AI models / Foundation models
    ("Art. 51", "GPAI Models",
     "Classification of GPAI models with systemic risk",
     "A general-purpose AI model shall be classified as having systemic risk if it has high-impact capabilities, evaluated on the basis of cumulative training compute (≥10^25 FLOP threshold) or designation by the Commission."),
    ("Art. 53", "GPAI Models",
     "Obligations for providers of GPAI models",
     "Providers of GPAI models shall draw up and keep up to date technical documentation of the model, provide information to downstream providers, comply with EU copyright law, and publish a sufficiently detailed summary of the training data."),
    ("Art. 54", "GPAI Models",
     "Authorised representatives for non-EU providers",
     "Providers of GPAI models established in third countries shall, prior to placing models on the EU market, appoint by written mandate an authorised representative established in the EU."),
    ("Art. 55", "GPAI Models",
     "Obligations for providers of GPAI models with systemic risk",
     "Providers of GPAI models with systemic risk shall additionally perform model evaluation, assess and mitigate systemic risks, track and report serious incidents, and ensure adequate cybersecurity protection."),
]

EU_AI_ACT_GOVERNANCE: list[tuple[str, str, str, str]] = [
    ("Art. 71", "Governance & Registration",
     "EU database for high-risk AI systems",
     "Providers (and where applicable deployers) shall register stand-alone high-risk AI systems listed in Annex III in the EU database before placing them on the market."),
    ("Art. 72", "Governance & Registration",
     "Post-market monitoring by providers",
     "Providers shall establish and document a post-market monitoring system that actively and systematically collects, documents and analyses data on the performance of high-risk AI systems."),
    ("Art. 73", "Governance & Registration",
     "Reporting of serious incidents",
     "Providers of high-risk AI systems placed on the EU market shall report any serious incident to the market surveillance authorities of the Member States, within prescribed timelines."),
    ("Art. 99", "Penalties",
     "Penalties — administrative fines",
     "Non-compliance with prohibited AI practices: up to €35M or 7% of worldwide annual turnover. Non-compliance with most other obligations: up to €15M or 3%. Supply of incorrect information: up to €7.5M or 1%."),
]


ALL_EU_AI_ACT_CONTROLS = (
    EU_AI_ACT_PROHIBITED
    + EU_AI_ACT_HIGH_RISK
    + EU_AI_ACT_PROVIDERS
    + EU_AI_ACT_TRANSPARENCY
    + EU_AI_ACT_GPAI
    + EU_AI_ACT_GOVERNANCE
)


async def seed_eu_ai_act(session: AsyncSession) -> None:
    """Idempotent EU AI Act seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="ai_governance",
        description=(
            "Regulation (EU) 2024/1689 — the EU AI Act. World's first comprehensive AI "
            "regulation, adopted June 2024 with phased applicability through August 2027. "
            "Establishes a risk-based framework: prohibited AI, high-risk AI, GPAI models, "
            "and limited-risk transparency obligations. Penalties up to €35M / 7% of global "
            "turnover (Art. 99)."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2024, 8, 1),  # entry into force
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_EU_AI_ACT_CONTROLS:
        session.add(Control(
            id=str(uuid.uuid4()),
            framework_version_id=version.id,
            control_code=control_code,
            category=category,
            title=title,
            description=description,
            rule_function=None,
        ))

    await session.flush()
