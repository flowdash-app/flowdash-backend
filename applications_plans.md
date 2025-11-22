
# 💰 FlowDash Master Plan: Detailed Pricing & Capability Tiers

The core strategy is to minimize risk and cost for free users while incentivizing upgrades for **reliability (Push Alerts)** and **scale (Multi-Instance/Team Access)**. All activity limits are enforced via your **Backend Bridge**.

## 1. 🟢 Tier 1: "FlowDash **Free**"

This tier is a strictly limited **monitoring trial**.

| Metric | Limit | Rationale |
| :--- | :--- | :--- |
| **Price** | **\$0 / Month** | Lead generation and feature trial. |
| **Data Freshness** | **10-minute data cache** (Cached data updates). | Reduces API load while providing reasonable data freshness. |
| **Alerting** | Status Polling Only (No Push Alerts). | Forces an upgrade for reliability. |
| **Activity (Control)** | **5 Toggles/Day** (Activate/Deactivate). | Limits active management; forces user to rely on the desktop. |
| **Activity (View)** | **20 List Refreshes/Day** (Workflows/Executions). | Protects your backend from excessive polling by free users. |
| **Error Views (Detailed)**| **3 Detailed Views/Day.** | Allows basic troubleshooting, but insufficient for heavy debugging. |
| **Trigger Buttons** | **1 Simple Mobile Trigger** (No forms). | Showcase feature. |
| **Instance Limit** | **1 n8n Instance** connected. | Limits use to solo-project testing. |

---

## 2. 🟡 Tier 2: "FlowDash **Pro**"

The primary target is the serious freelancer or power user. The upgrade is driven by **Instant Reliability**.

| Metric | Suggested Price | Capability / Limit | Value Proposition |
| :--- | :--- | :--- | :--- |
| **Price** | **\$15 - \$20 / Month** | Unlocks the *reliability* needed for production automations. |
| **Data Freshness** | **3-minute data cache** (Near real-time data). | Fresher data for better decision-making while maintaining performance. |
| **Alerting** | **INSTANT PUSH NOTIFICATIONS** (Via Serverless Webhooks). | **The Killer Feature:** Prevents financial/data loss due to slow error detection. |
| **Activity (Control)** | **100 Toggles/Day.** | Sufficient for heavy daily management without friction. |
| **Activity (View)** | **200 List Refreshes/Day.** | Allows for heavy, continuous monitoring. |
| **Error Views (Detailed)**| **Unlimited** Detailed Execution Views. | Enables professional, unrestricted on-the-go debugging. |
| **Trigger Buttons** | **10 Custom Triggers** (Forms & Buttons). | Supports multiple daily actions and custom forms. |
| **Instance Limit** | **Up to 5 n8n Instances** connected. | Allows management of a small client portfolio. |

---

## 3. 🟠 Tier 3: "FlowDash **Business**"

Designed for small teams and agencies, focused on **Scale, Team Security, and Accountability**.

| Metric | Suggested Price | Capability / Limit | Value Proposition |
| :--- | :--- | :--- | :--- |
| **Price** | **\$50 - \$75 / Month** | Based on unlocking scale and adding team management seats. |
| **Data Freshness** | **3-minute data cache** (Near real-time data). | Fresher data for better decision-making while maintaining performance. |
| **Alerting** | **Unlimited** Instant Push Notifications. | Unrestricted use across high-volume systems. |
| **Activity/View** | **Unlimited** Toggles and List Refreshes. | Zero friction for constant use by multiple users. |
| **Team Management** | **5 User Seats Included** (with role-based access control - View-Only/Control). | Essential for managing client access and internal segregation of duties. |
| **Instance Limit** | **Unlimited** n8n Instances. | Critical for agencies managing numerous client projects. |
| **Compliance** | **Audit Logging** for all mobile actions. | Provides necessary accountability for business operations. |

---

### 4. ⚫ Tier 4: "FlowDash **Enterprise**"

This tier provides a high-value, bespoke service for large organizations with unique requirements.

| Metric | Suggested Price | Capability / Limit | Value Proposition |
| :--- | :--- | :--- | :--- |
| **Price** | **Custom Quote (Starting at \$500+/Month)** | High-revenue, bespoke solutions. |
| **Data Freshness** | **Real-time data (no caching)** (Always fresh, instant updates). | Premium real-time experience with zero caching overhead for critical operations. |
| **Custom Development** | **Dedicated Engineering Time** (e.g., 20 hours/month included). | Building custom Flutter screens for unique internal use cases (e.g., integrating with their internal SSO or custom node configurations). |
| **Deployment** | **On-Premise or Private Cloud Deployment.** | Addresses strict security and regulatory needs (e.g., data isolation). |
| **SLA** | **99.99% Guaranteed Uptime Service Level Agreement.** | Critical for organizations with high availability requirements. |
