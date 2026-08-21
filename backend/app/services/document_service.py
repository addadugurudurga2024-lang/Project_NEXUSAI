"""
Document Analysis Pipeline Service
Architecture:
  DocumentService → Extractor → TextPreprocessor → AIAnalyzer → IssueClassifier → RecommendationMapper → MongoDB
"""
import os
import re
from datetime import datetime
from typing import Dict, Any, List
from app.core.config import settings


# ─── Text Extraction ────────────────────────────────────────────────────────

def extract_text(file_path: str, file_type: str) -> str:
    """Extract text from supported file types."""
    text = ""
    try:
        if file_type == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            doc.close()
        elif file_type == ".docx":
            from docx import Document
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif file_type == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif file_type == ".csv":
            import pandas as pd
            df = pd.read_csv(file_path)
            text = df.to_string()
        elif file_type == ".xlsx":
            import pandas as pd
            df = pd.read_excel(file_path)
            text = df.to_string()
    except Exception as e:
        text = f"[Extraction error: {str(e)}]"
    return text


# ─── Text Preprocessing ─────────────────────────────────────────────────────

def preprocess_text(text: str) -> str:
    """Clean and normalize text for analysis."""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text[:15000]  # Limit to 15k chars for analysis


# ─── Demo Analysis (Pattern-based NLP) ──────────────────────────────────────

AMBIGUITY_PATTERNS = [
    (r'\b(as soon as possible|ASAP|when possible|at some point)\b', "Vague timing requirement — no specific deadline"),
    (r'\b(appropriate|suitable|reasonable|adequate)\b', "Subjective qualifier — criteria not defined"),
    (r'\b(etc\.?|and so on|and others)\b', "Incomplete enumeration — list not fully specified"),
    (r'\b(should|may|might|could)\b(?! not)', "Weak modal verb — requirement may not be mandatory"),
    (r'\b(fast|quickly|efficiently|high[- ]performance)\b', "Performance requirement without measurable criteria"),
    (r'\b(easy|simple|user[- ]friendly|intuitive)\b', "Usability requirement without acceptance criteria"),
    (r'\b(all|every|always|never)\b', "Absolute term — may be overly broad or unrealistic"),
    (r'\b(the system|it)\s+will\b', "Pronoun reference — subject may be ambiguous"),
]

SECURITY_PATTERNS = [
    (r'\b(password|credential|secret|token|API key)\b', "Credential handling — review for secure storage requirements"),
    (r'\b(login|authentication|authorization|access control)\b', "Authentication requirement — verify security specifications"),
    (r'\b(data|personal|PII|sensitive)\b', "Data sensitivity — verify privacy and compliance requirements"),
    (r'\b(encrypt|SSL|TLS|HTTPS)\b', "Encryption requirement — verify cipher/protocol specifications"),
    (r'\b(admin|superuser|root|privilege)\b', "Elevated privilege — verify access control requirements"),
    (r'\b(third[- ]party|external|vendor|integration)\b', "Third-party dependency — verify security vetting process"),
]

COMPLETENESS_PATTERNS = [
    (r'\b(TBD|TBC|TODO|to be defined|to be confirmed|to be determined)\b', "Undefined requirement — content marked as TBD"),
    (r'\b(see|refer to|refer|as per)\b', "Reference-only requirement — referenced document not included"),
    (r'\b(acceptance criteria|test criteria|validation)\b', "Acceptance criteria mentioned — verify complete specification"),
    (r'\b(error|exception|failure|fault)\b', "Error handling — verify error scenarios are specified"),
]

DOMAIN_KEYWORDS = {
    "Cybersecurity": ["password", "auth", "login", "encrypt", "SSL", "TLS", "credential", "token", "privilege", "access control", "security", "PII", "data protection"],
    "Backend": ["API", "server", "service", "endpoint", "database query", "backend", "microservice", "REST", "GraphQL"],
    "Frontend": ["UI", "UX", "interface", "button", "form", "page", "screen", "user interface", "React", "Angular"],
    "Database": ["database", "schema", "table", "query", "index", "migration", "SQL", "MongoDB", "data model"],
    "QA": ["test", "testing", "validation", "acceptance criteria", "quality", "bug", "defect"],
    "DevOps": ["deploy", "deployment", "CI/CD", "pipeline", "container", "Docker", "Kubernetes", "cloud"],
    "Business Analysis": ["requirement", "business rule", "stakeholder", "process", "workflow", "policy"],
    "UI/UX": ["design", "usability", "user experience", "wireframe", "prototype", "accessibility"],
    "Project Management": ["deadline", "timeline", "milestone", "resource", "budget", "scope"],
}

SPECIALIST_MAP = {
    "Cybersecurity": "Cybersecurity Specialist",
    "Backend": "Backend Engineer",
    "Frontend": "Frontend Engineer",
    "Database": "Database Engineer",
    "QA": "QA Engineer",
    "DevOps": "DevOps Engineer",
    "Business Analysis": "Business Analyst",
    "UI/UX": "UI/UX Designer",
    "Project Management": "Project Manager",
}

SEVERITY_RULES = {
    "Cybersecurity": "high",
    "Backend": "medium",
    "Frontend": "low",
    "Database": "medium",
    "QA": "medium",
    "DevOps": "medium",
    "Business Analysis": "medium",
    "UI/UX": "low",
    "Project Management": "medium",
}


def _classify_domain(text_snippet: str) -> str:
    scores = {}
    lower = text_snippet.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in lower)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "Business Analysis"
    return max(scores, key=scores.get)


def _demo_analysis(text: str, filename: str) -> List[Dict]:
    """
    Pattern-based NLP analysis — DEMO ANALYSIS MODE.
    Clearly identified as demo/heuristic, not real LLM output.
    """
    issues = []
    issue_id = 1
    lines = text.split('. ')

    for pattern, description in AMBIGUITY_PATTERNS:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                snippet = line.strip()[:200]
                domain = _classify_domain(line)
                issues.append({
                    "issue_id": f"DEMO-{issue_id:03d}",
                    "type": "Requirement Ambiguity",
                    "title": description,
                    "description": f"The following text contains potentially ambiguous language: \"{snippet[:120]}...\"",
                    "evidence": snippet,
                    "severity": "medium",
                    "domain": domain,
                    "recommended_specialist": SPECIALIST_MAP.get(domain, "Business Analyst"),
                    "suggested_action": "Clarify this requirement with stakeholders and define measurable acceptance criteria.",
                })
                issue_id += 1
                if issue_id > 5:
                    break
        if issue_id > 5:
            break

    for pattern, description in SECURITY_PATTERNS:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                snippet = line.strip()[:200]
                domain = "Cybersecurity"
                issues.append({
                    "issue_id": f"DEMO-{issue_id:03d}",
                    "type": "Potential Security Concern",
                    "title": description,
                    "description": f"Security-sensitive content identified: \"{snippet[:120]}...\"",
                    "evidence": snippet,
                    "severity": "high",
                    "domain": domain,
                    "recommended_specialist": SPECIALIST_MAP[domain],
                    "suggested_action": "Review security requirements with a Cybersecurity Specialist to ensure proper controls are specified.",
                })
                issue_id += 1
                if issue_id > 10:
                    break
        if issue_id > 10:
            break

    for pattern, description in COMPLETENESS_PATTERNS:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                snippet = line.strip()[:200]
                domain = _classify_domain(line)
                issues.append({
                    "issue_id": f"DEMO-{issue_id:03d}",
                    "type": "Missing Information",
                    "title": description,
                    "description": f"Incomplete specification detected: \"{snippet[:120]}...\"",
                    "evidence": snippet,
                    "severity": "medium",
                    "domain": domain,
                    "recommended_specialist": SPECIALIST_MAP.get(domain, "Business Analyst"),
                    "suggested_action": "Complete this specification before development begins.",
                })
                issue_id += 1
                if issue_id > 15:
                    break
        if issue_id > 15:
            break

    return issues[:12]  # Max 12 issues per analysis


async def _llm_analysis(text: str) -> List[Dict]:
    """Real LLM-based analysis using configured AI provider."""
    import httpx

    system_prompt = """You are an expert project analyst. Analyze the provided project document and identify:
1. Requirement ambiguities
2. Missing requirements or acceptance criteria
3. Conflicting requirements
4. Incomplete specifications
5. Potential security concerns
6. Terminology inconsistencies

For each issue found, respond in JSON format as a list of objects with fields:
- type: (Requirement Ambiguity | Missing Information | Conflicting Requirements | Potential Security Concern | Incomplete Specification)
- title: brief issue title
- description: detailed description
- evidence: exact quote from document
- severity: (low | medium | high | critical)
- domain: (Backend | Frontend | Database | Cybersecurity | DevOps | QA | Business Analysis | UI/UX | Project Management)
- suggested_action: recommended corrective action

Return ONLY valid JSON array."""

    user_prompt = f"Analyze this project document:\n\n{text[:8000]}"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.ai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
            }
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        # Parse JSON from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            import json
            issues_raw = json.loads(json_match.group())
            for i, issue in enumerate(issues_raw):
                domain = issue.get("domain", "Business Analysis")
                issue["issue_id"] = f"AI-{i+1:03d}"
                issue["recommended_specialist"] = SPECIALIST_MAP.get(domain, "Business Analyst")
            return issues_raw
        return []


# ─── Main Pipeline ───────────────────────────────────────────────────────────

async def analyze_document_pipeline(doc: dict, db) -> Dict[str, Any]:
    """Full document analysis pipeline."""
    document_id = str(doc["_id"])
    file_path = doc.get("storage_path", "")
    file_type = doc.get("file_type", ".txt")
    filename = doc.get("original_filename", "document")

    # Step 1: Extract text
    raw_text = extract_text(file_path, file_type)
    processed_text = preprocess_text(raw_text)

    # Step 2: Determine analysis mode
    use_llm = bool(settings.ai_api_key and len(settings.ai_api_key) > 10)
    analysis_mode = "LLM" if use_llm else "DEMO"

    # Step 3: Run analysis
    issues = []
    analysis_error = None
    if use_llm:
        try:
            issues = await _llm_analysis(processed_text)
            analysis_mode = "LLM"
        except Exception as e:
            analysis_error = str(e)
            issues = _demo_analysis(processed_text, filename)
            analysis_mode = "DEMO (LLM fallback)"
    else:
        issues = _demo_analysis(processed_text, filename)

    # Step 4: Enrich issues
    for issue in issues:
        domain = issue.get("domain", "Business Analysis")
        if not issue.get("recommended_specialist"):
            issue["recommended_specialist"] = SPECIALIST_MAP.get(domain, "Business Analyst")
        if not issue.get("severity"):
            issue["severity"] = SEVERITY_RULES.get(domain, "medium")

    # Step 5: Persist to MongoDB
    analysis_doc = {
        "document_id": document_id,
        "project_id": doc.get("project_id"),
        "filename": filename,
        "analysis_mode": analysis_mode,
        "is_demo": analysis_mode != "LLM",
        "total_issues": len(issues),
        "issues": issues,
        "text_length": len(processed_text),
        "summary": _generate_summary(issues, filename, analysis_mode),
        "analysis_error": analysis_error,
        "created_at": datetime.utcnow(),
    }

    await db.document_analysis.replace_one(
        {"document_id": document_id},
        analysis_doc,
        upsert=True,
    )

    analysis_doc["id"] = document_id
    return analysis_doc


def _generate_summary(issues: List[Dict], filename: str, mode: str) -> str:
    total = len(issues)
    high = sum(1 for i in issues if i.get("severity") in ["high", "critical"])
    medium = sum(1 for i in issues if i.get("severity") == "medium")
    domains = list(set(i.get("domain") for i in issues))

    return (
        f"Analysis of '{filename}' detected {total} potential issue(s): "
        f"{high} high/critical severity, {medium} medium severity. "
        f"Domains affected: {', '.join(domains) if domains else 'None'}. "
        f"Analysis mode: {mode}."
    )
