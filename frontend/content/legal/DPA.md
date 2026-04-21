# Data Processing Agreement (DPA)

**This Data Processing Agreement (“Agreement”)** is entered into between **the Customer** (the company registering for AI CV Scanner, acting as **data controller** under the GDPR) and **AI CV Scanner** (the **processor**).

By accepting the Agreement in the product (or by accepting the Terms of Service where acceptance is stated to incorporate this DPA), the Customer appoints AI CV Scanner to process **CV Data** as described below.

---

## 1. DEFINITIONS

**“Personal Data”** means any information relating to an identified or identifiable natural person, as defined in Regulation (EU) 2016/679 (“**GDPR**”).

**“CV Data”** means Personal Data contained in curriculum vitae files and extracted text used solely to produce ranking outputs for the Customer, including filenames and any metadata required to operate the service.

**“Processing”** means any operation or set of operations performed on Personal Data, whether or not by automated means, including collection, storage, retrieval, use, disclosure, erasure, or destruction.

**“GDPR”** means the General Data Protection Regulation (EU) 2016/679, as transposed or applied in EU Member States (including Ireland).

**“Sub-processor”** means a third party engaged by the processor to process Personal Data on behalf of the Customer.

---

## 2. SCOPE AND PURPOSE

2.1 AI CV Scanner shall process CV Data **only on documented instructions from the Customer**, unless EU or Member State law requires otherwise (in which case AI CV Scanner shall inform the Customer of that legal requirement unless prohibited).

2.2 The **purpose** of processing is to enable the Customer to **upload CVs**, **extract text**, and **generate advisory ranking scores and short explanatory reasoning** for HR review against job requirements configured by the Customer.

2.3 AI CV Scanner shall not use CV Data for any other purpose, including marketing, profiling unrelated to the service, or model training (subject to the Sub-processor terms below).

---

## 3. DURATION

3.1 This Agreement remains in effect for so long as AI CV Scanner processes Personal Data on behalf of the Customer.

3.2 Upon termination of the Customer’s account or expiry of the processing relationship, AI CV Scanner shall **delete or return** Personal Data in accordance with the Technical and Organisational Measures and the deletion procedures described in this Agreement and the Terms of Service, **within thirty (30) days** unless a shorter period applies for specific data classes (for example, raw CV blobs may be deleted sooner after ranking completes).

---

## 4. DATA DELETION (ARTICLE 17)

4.1 The service provides **one-click deletion** capabilities, including deletion of a job posting and its associated CV records and encrypted files, and **complete account deletion** to erase tenant-held data subject to propagation and backup cycles described in security documentation.

4.2 Where the Customer requests deletion under Article 17 GDPR, AI CV Scanner shall **delete CV Data in blob storage without undue delay** where technically feasible, and shall delete associated database records held as processor for the Customer, except where EU law requires retention.

4.3 Upon completed deletion operations initiated by an authorized Customer administrator, AI CV Scanner shall provide **confirmation in writing** (including by email or in-product confirmation) that the deletion request was executed, stating the scope of deletion to the extent technically observable.

---

## 5. CONFIDENTIALITY

5.1 AI CV Scanner ensures that persons authorized to process Personal Data are bound by **confidentiality** obligations.

5.2 **No human access** to CV content is used for ordinary service operations. Access may occur **only** for **security debugging** using **controlled logs** and under least-privilege administrative policies, and only where necessary to maintain integrity, confidentiality, and availability.

---

## 6. SUB-PROCESSORS

The Customer authorizes AI CV Scanner to engage Sub-processors as follows:

### 6.1 OpenAI API

- **Purpose:** advisory scoring and reasoning generation from extracted CV text and job requirements.
- **Location / transfers:** processing location and subprocessors are determined by **OpenAI**’s applicable terms and the **Customer’s** OpenAI account / API configuration. The Customer shall configure processing in line with its transfer and residency requirements.
- **Terms:** OpenAI’s data processing terms apply as between OpenAI and AI CV Scanner. The Customer should disable or restrict uses of Customer content for model training where OpenAI offers such controls.

### 6.2 MongoDB Atlas

- **Purpose:** storage of account, job, and CV **metadata** (for example, filenames, statuses, scores, reasoning text).
- **Region:** **EU** cluster / region (Customer configuration required). MongoDB Atlas DPA applies as between MongoDB and AI CV Scanner.

### 6.3 S3-compatible object storage

- **Purpose:** storage of **encrypted** CV file blobs (ciphertext only at rest in the bucket).
- **Region:** **EU** bucket / region or EU-capable provider (Customer configuration required). The applicable cloud provider’s data protection terms apply as between that provider and AI CV Scanner.

### 6.4 Stripe Payments

- **Purpose:** payment processing and billing records.
- **Data:** **no CV Data** is sent to Stripe.

AI CV Scanner shall provide notice of changes to Sub-processors where required and shall impose data protection terms materially consistent with Article 28 GDPR.

---

## 7. SECURITY MEASURES

AI CV Scanner implements appropriate technical and organizational measures, including:

- **AES-256 encryption at rest** for CV blobs prior to storage;
- **TLS** for data in transit;
- **strict tenant isolation** so queries are scoped to the Customer’s `company_id`;
- **audit logging** of security-relevant administrative events as applicable to the platform.

---

## 8. DATA BREACH NOTIFICATION

AI CV Scanner shall notify the Customer **without undue delay** and in any event **within seventy-two (72) hours** after becoming aware of a Personal Data breach affecting CV Data processed on behalf of the Customer, where feasible in accordance with Article 33 GDPR, and shall provide information reasonably necessary for the Customer to meet its obligations.

---

## 9. DATA SUBJECT RIGHTS

AI CV Scanner shall assist the Customer, by appropriate technical and organizational measures, in fulfilling requests to exercise rights under **Articles 12–22 GDPR**, insofar as possible, considering the nature of processing.

---

## 10. RIGHT NOT TO BE SUBJECT TO AUTOMATED DECISIONS

10.1 Outputs are **advisory** and intended to assist HR prioritization.

10.2 The Customer acknowledges that **human decision-makers** make hiring decisions and that **all CVs remain visible** in the application; the system does not implement solely automated decisions that produce legal or similarly significant effects within the meaning of Article 22 GDPR.

10.3 Candidates may request **human review** via the Customer (controller). AI CV Scanner will assist the Customer in responding where processing assistance is required.

---

## 11. DATA EXPORT

Upon the Customer’s request, AI CV Scanner shall provide a **machine-readable export** of metadata held for the Customer’s tenant **within thirty (30) days**, subject to reasonable security verification.

---

## 12. COMPLIANCE VERIFICATION

The Customer may audit AI CV Scanner’s compliance with this Agreement **no more than once per twelve (12) months** (unless required by supervisory authority), upon reasonable notice and subject to confidentiality and security controls. AI CV Scanner may satisfy audit requests by providing **certificates** and **summaries** where appropriate.

---

## 13. GOVERNING LAW

This Agreement is governed by the laws of **Ireland**, without regard to conflict-of-law rules.

---

## 14. ACCEPTANCE

This Agreement is accepted by the Customer when the Customer **accepts the Terms of Service** (or otherwise accepts this DPA in-product) on behalf of the Customer entity.

---

*This document is provided as a template for product implementation. Independent legal advice is recommended before reliance in production.*
