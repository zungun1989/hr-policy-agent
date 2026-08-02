# Data Security Policy
**Document ID:** POL-006  
**Effective Date:** January 1, 2025  
**Last Reviewed:** November 2024  
**Owner:** IT Security & Compliance

---

## 1. Purpose

This policy establishes the requirements for protecting Acme Corp's data, systems, and infrastructure from unauthorized access, disclosure, modification, or destruction. All employees, contractors, and third-party vendors with access to Acme Corp systems must comply.

---

## 2. Data Classification

All data handled by Acme Corp employees must be classified into one of four categories:

| Classification | Description | Examples |
|---|---|---|
| **Public** | Approved for external release | Marketing materials, published blog posts |
| **Internal** | For use within Acme Corp only | Company announcements, general policies |
| **Confidential** | Restricted to authorized employees | Financial reports, employee data, customer data |
| **Restricted** | Highest sensitivity; access on need-to-know only | PII, payment card data, trade secrets |

Employees must handle data according to its classification. When in doubt, treat data as Confidential.

---

## 3. Device Security

### 3.1 Company-Issued Devices

- All company laptops must have full-disk encryption enabled (BitLocker for Windows, FileVault for macOS). IT enables this during provisioning.
- Laptops must auto-lock after **5 minutes** of inactivity.
- Employees must not disable security software (antivirus, EDR agent, MDM).
- Company devices must receive OS and security updates within **72 hours** of release.

### 3.2 Personal Devices (BYOD)

Personal devices used to access Acme Corp email, Slack, or any corporate system must:
- Enroll in Acme Corp's Mobile Device Management (MDM) system
- Have a passcode or biometric lock enabled
- Run a supported OS version (per IT's compatibility list)
- Have remote wipe capability enabled (enforced by MDM)

Personal devices are never permitted to access Restricted data.

---

## 4. Password and Authentication

- All accounts must use passwords of at least **14 characters** with mixed case, numbers, and symbols, or a passphrase of at least 20 characters.
- Passwords must not be reused from the previous 10 passwords.
- All Acme Corp accounts with system or data access must enable **Multi-Factor Authentication (MFA)**.
- Employees must use the Acme Corp password manager (1Password enterprise) for storing credentials. Passwords must not be stored in plaintext files, spreadsheets, or email.
- Shared credentials are prohibited. Every employee must have a unique login.

---

## 5. Network Security

### 5.1 VPN

- All remote access to Acme Corp internal systems requires the use of the company VPN (GlobalProtect).
- VPN must remain active whenever accessing internal tools (Jira, Confluence, internal APIs, HR systems).
- Employees working internationally must use the designated international VPN endpoint provided by IT.

### 5.2 Wi-Fi

- Public Wi-Fi networks (coffee shops, hotels, airports) must not be used without VPN active.
- Home networks must use WPA2 or WPA3 encryption. Employees on public/hotel Wi-Fi must activate VPN before any work activity.

---

## 6. Data Handling

### 6.1 Storage

- Confidential and Restricted data must be stored in approved Acme Corp systems (Google Drive with appropriate sharing settings, internal databases, or encrypted file storage).
- Confidential or Restricted data must not be stored on personal devices, personal cloud storage (personal Google Drive, Dropbox personal, iCloud), or USB drives without IT approval.

### 6.2 Sharing

- Confidential data may be shared internally via approved tools with appropriate access controls.
- Sharing Confidential or Restricted data externally (with vendors, clients, or partners) requires a signed NDA or Data Processing Agreement (DPA) and manager approval.
- Employees must not email Restricted data. Use the Acme Corp secure file sharing portal (SecureShare) instead.

### 6.3 Disposal

- Physical documents containing Confidential or Restricted data must be shredded using cross-cut shredders.
- Digital data must be deleted using approved secure deletion methods. Employees must not simply delete files from their desktop.
- Devices must be returned to IT for secure wiping before disposal or reuse.

---

## 7. Software and Application Security

- Employees may only install software approved by IT. See the approved software list in the IT portal.
- Downloading or installing unauthorized software, browser extensions, or tools that access company data is prohibited.
- AI tools (ChatGPT, Copilot, etc.) must not be used to process Confidential or Restricted data. See the AI Tools Policy addendum.

---

## 8. Phishing and Social Engineering

- Employees must report suspicious emails to security@acmecorp.com or via the PhishAlarm button in email clients.
- Employees must never click links or download attachments from unverified senders.
- Employees must never provide login credentials, MFA codes, or sensitive information over phone, email, or messaging — even to someone claiming to be from IT or HR.

---

## 9. Security Incident Reporting

Any suspected security incident must be reported to IT Security **within 1 hour** of discovery:
- Email: security@acmecorp.com
- Emergency hotline: 1-800-555-SEC1 (24/7)
- Slack: #security-incidents

A security incident includes: lost or stolen devices, unauthorized access, data exposure, phishing click, malware infection, or any unusual system behavior.

---

## 10. Remote Work Security

Remote workers have additional security obligations per Section 5 of the Remote Work Policy (POL-002). All requirements in that policy apply in addition to this policy.

---

## 11. Violations

Security policy violations may result in disciplinary action up to and including termination and, where applicable, legal action. Intentional data breaches or exfiltration of company data will be referred to law enforcement.

---

## 12. Questions

Contact IT Security at security@acmecorp.com.
