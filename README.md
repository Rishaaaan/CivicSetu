

<img src="media/1.jpg" id="1">
#CivicSetu: A Crowdsourced Civic Issue  Reporting and Resolution System
###Team ID: TID 212 
###Problem Statement ID: 25031 
#### This website is LIVE and hosted on render.com at 
#### https://civicconnect-th20.onrender.com/
#### username: admintester00@gmail.com
#### password: AdminTester00

##User Interface
Admin Login

Admins securely log in to manage reports, monitor activity, and track overall system usage

<img src="media/image1.jpeg" id="image1">

Dashboard Overview

Provides a snapshot of total issues, categories, status, and quick access to pending actions.

<img src="media/image2.jpeg" id="image2">

<img src="media/image3.jpeg" id="image3">Navigating the Interface

Simple, mobile-first design ensures users and admins can move between sections easily.

Registration of user

<img src="media/image4.jpeg" id="image4">

Creating a Report

<img src="media/image5.jpeg" id="image5">

Filtering Reports

<img src="media/image6.jpeg" id="image6">

Navigation

<img src="media/image7.jpeg" id="image7">

Department Visibility

<img src="media/image8.jpeg" id="image8">

<img src="media/image9.jpeg" id="image9">Priority


1. Introduction 
CivicSetu is an innovative, AI-powered platform designed to streamline civic issue  reporting and resolution for the Government of Jharkhand, with the potential for  nationwide scalability. The system bridges the critical communication gap between  citizens and municipal authorities, providing a transparent, efficient, and accountable  mechanism for addressing everyday problems like potholes, broken streetlights, and  overflowing garbage. 
This mobile-first solution empowers citizens to report issues effortlessly through multi modal inputs, including photos, speech-to-text, and text. The platform’s AI-driven  backend automatically processes, categorizes, and routes these reports to the correct  municipal departments, ensuring prompt and targeted action. By leveraging advanced  AI, a rewarding system, and community-driven mechanisms, CivicSetu aims to foster  greater transparency, accountability, and public trust in governance. 



2. Problem Statement 
Local governments often struggle with the timely identification, prioritization, and  resolution of civic issues. The current grievance redress systems are typically slow,  fragmented, and lack transparency, leading to delays, duplicated complaints, and  inefficient resource allocation. Citizens, despite encountering these problems daily, lack  an effective and scalable channel to report them. CivicSetu addresses these systemic  gaps by offering a streamlined, mobile-first solution that combines citizen-driven  reporting with AI-powered processing.

3. Proposed Solution: CivicSetu 
CivicSetu is a crowdsourced reporting and resolution system with a dual objective:  empowering citizens and ensuring an efficient municipal response. The platform  consists of two main components: a mobile application for citizens and a web-based  administrative dashboard for municipal authorities. 
4.Key Features 
∙ Multi-modal Input: Citizens can submit reports using photos, speech-to-text,  and text, with automatic location tagging for accurate issue pinpointing. ∙ AI-driven Prioritization: An intelligent engine predicts the severity and urgency  of reported issues, enabling authorities to focus on the most critical problems  first.(80% accuracy) 
∙ Translation Services: The platform supports multilingual reporting and provides  speech-to-text and text translation to ensure inclusivity. 
∙ Admin Dashboards: A comprehensive dashboard provides municipal staff with  tools for categorization, task routing, live map views, and real-time resolution  tracking. 
∙ Chatbot Assistant: Providing municipal staff with an AI-suggested solution  assistant. 
∙ Context-aware Deduplication: Basic clustering based on location and content  helps group similar reports, reducing duplicate complaints and identifying issue  hotspots. 
∙ User-Friendly UI 
o Simple and intuitive design, ensuring easy navigation. 
o Built-in translator for multilingual accessibility. 
o Speech-to-text feature for quick reporting without typing. 
o Minimal steps to submit issues, avoiding complex workflows. 
o Strong focus on bridging the communication gap between citizens and  authorities through clear feedback loops.
Leaderboard highlights top reporters in the community, ranked by the number of issues submitted. It motivates citizens by recognizing their contributions and promoting healthy competition







5. Methodology & Technical Approach 
The CivicSetu system operates through a seamless, automated workflow: 
1. Citizen Reporting: A user captures and submits an issue via the mobile app  using photos, audio, video, or text. 
2. Metadata Enrichment: The report is automatically enriched with metadata such  as GPS coordinates and timestamps. 
3. AI Processing: AI services (image captioning, speech-to-text, and translation)  generate a unified, standardized issue description. 
4. Clustering & Prioritization: The system uses radius-based clustering to group  similar reports by location and content. A prioritization engine then analyzes severity, historical data, and context to predict urgency. 
5. Automated Routing: Reports are automatically routed to the relevant municipal  departments based on the issue category. 
6. Administrator Action: Administrators view real-time dashboards with clustered  issues and actionable insights to manage their workload efficiently. 7. Citizen 7.Updates: Citizens receive real-time progress updates and resolution  confirmations throughout the issue lifecycle. 
8. Feedback Loop: Resolved case data is used to continuously retrain and  improve the AI models, ensuring the system adapts to changing urban dynamics. 

6. Feasibility & Viability 
CivicSetu is a mobile-first, cloud-enabled solution built for scalability, reliability, and cost  efficiency. Its modular architecture supports seamless integ. 
ration with existing municipal  e-governance systems via open APIs and allows for easy expansion to new cities  without major re-engineering. This makes it a highly viable and sustainable solution for  adoption across India


7. Impact & Benefits 
 For Citizens: Provides an easy, transparent, and efficient way to report issues  and receive real-time updates. 
For Administrators: Reduces redundant workloads, prioritizes tasks with AI powered insights, and improves overall workload management. 
 For Governance: Optimizes resource allocation, enhances public safety, and  builds trust with citizens.
 For Communities: Fosters cleaner and safer environments through active civic  engagement. 
 For Scalability: Offers a replicable and adaptable model for any Indian city. 

For engagement:The Leaderboard will enhance engagement by motivating citizens to actively report issues, fostering healthy competition, and building a sense of community contribution
CivicSetu provides a clear visual of issue hotspots and helps allocate resources  efficiently by focusing on high-density clusters of civic issues. 
8. Novelty 
CivicSetu distinguishes itself through several unique features: 
∙ Multi-modal Integration: Combines text, speech, image, and video inputs for  comprehensive reporting. 
∙ Offline-first Capability: Stores reports locally using SQLite + Room and syncs  automatically when internet is available. 
∙ Context-aware: Uses geospatial and semantic clustering to manage duplicate  complaints effectively. 
∙ AI-driven Prioritization: Dynamically predicts issue urgency based on severity,  accident mentions, and historical patterns. 
∙ Leaderboards.: Encourages sustained citizen engagement through  reward systems and leaderboards. 
∙ Dynamic Clustering: Radius-based clustering helps authorities identify  hotspots, with adjustable parameters as per urban density. 
∙ Predictive Analytics: Future problem forecasting (e.g., identifying roads at risk  of damage due to weather/traffic conditions). 
∙ Fraud Detection Mechanism: Flags false or malicious reports, ensuring system  integrity. 
∙ Multilingual Accessibility: In-built translator and speech-to-text features allow  reporting in regional languages. 
∙ Chatbot Integration: Assists administrators by suggesting practical solutions for  frequently recurring issues. 

9. Future Scope 
The future development of CivicSetu includes: 
Predictive Problem Modeling: Forecasting potential civic issues (e.g.,  predicting pothole formation based on traffic and weather data). 
Enhanced Multimedia: Expanding support for audio and video uploads. 
App Translation: Enabling the application to support all regional languages,  ensuring inclusivity and accessibility for citizens across Pan-India, not limited to  Jharkhand. 
∙ Notification: Citizens will receive timely notifications about route changes or  diversions caused by broken roads and related civic issues.

10. Sustainability 
CivicSetu is built on a foundation of long-term sustainability. It leverages open-source  frameworks and a cost-efficient cloud infrastructure, ensuring low operational costs. The  self-learning AI models adapt to changing urban dynamics, and the citizen engagement  mechanisms ensure continued adoption. Strategic collaboration with municipal bodies  guarantees the platform's relevance and long-term viability. 
11. Technical Stack
∙ Mobile Application: Kotlin (Android) with SQLite + Room for offline storage and  auto-sync. 
∙ Backend: Django (Python) for API, authentication, task routing, and clustering. ∙ AI/ML Services: Hugging Face for NLP, speech-to-text, translation, image  captioning, and prioritization (text classification). 
∙ Database & Cloud: Firebase for real-time sync, notifications, and scalable  storage. 
∙ Web Dashboard: Django Admin + HTML, CSS, and JavaScript for municipal  staff dashboards. 






12. Current Progress 
The team is currently focused on developing key functionalities: 
∙ Fraud Detection: Implementing features to identify irrelevant or malicious  reports. 
∙ Notifications: Ensuring citizens receive timely updates at every stage of their  report's lifecycle. 
∙ Rewarding System: Features like leaderboards, history pages, and reward  systems encourage citizen engagement and active participation. 
.Dashboard of Analytics:The Dashboard of Analytics provides real-time insights into reported issues, resolution rates, department performance, and citizen participation trends.

12. Conclusion 
CivicSetu is more than a reporting tool; it is a catalyst for clean, green, and accountable  governance. By seamlessly blending cutting-edge AI technology with active citizen  participation, CivicSetu transforms how local governments respond to everyday  challenges. The solution perfectly aligns with the SIH 2025 theme of Clean & Green  Technology and directly addresses Problem Statement ID 25031. With its focus on  scalability, sustainability, and innovation, CivicSetu has the potential to become a model  civic-tech platform for India, empowering citizens and authorities alike to build a better  future, together.

