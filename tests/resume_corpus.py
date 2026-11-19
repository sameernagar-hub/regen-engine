"""Resumes of many kinds (fictional people and companies) with the family each should read as.

Used by tests/test_resume_nlp.py for the Python classifier and, through node, for the web port. Several are traps:
a salesperson and an accountant at software companies, a recruiter who hires software engineers, a teacher turned
developer, a student with no jobs yet, a resume pasted as one line, one without section headers, and gibberish.
"""

CORPUS = [
    ("sales", """Jordan Taylor Chicago, IL • 555-0100 • name@example.com • linkedin.com/in/example
Summary
Quota-crushing Account Executive with 5+ years of B2B SaaS sales experience closing mid-market and enterprise deals. Skilled in full-cycle consultative selling, executive negotiation, and multi-threading complex accounts.
Core Competencies
* Sales Methodologies: MEDDIC, Challenger Sale, Sandler Selling System, Consultative & Value-Based Selling
* Pipeline & Closing: Full-Cycle Sales, Cold Outbound Prospecting, Enterprise Discovery, Contract Negotiation, Account Expansion & Upselling
* Sales Tech Stack: Salesforce CRM, HubSpot, Outreach, Gong, LinkedIn Sales Navigator, ZoomInfo, DocuSign
Experience
Senior Account Executive | Veloce Cloud Software | Chicago, IL
March 2024 – Present
* Achieved 132% of annual quota ($1.45M closed-won ARR against a $1.1M target) in FY2025, earning President's Club honors.
* Managed full-cycle enterprise sales for workflow automation software, navigating complex procurement cycles with VP and C-level stakeholders.
* Shortened average deal cycle from 68 days to 49 days by standardizing mutual action plans and upfront technical discovery.
Account Executive, Mid-Market | BrightPath Analytics | Chicago, IL
June 2022 – February 2024
* Closed $890K in net-new ARR across 34 mid-market accounts, finishing at 118% of quota in FY2023.
* Mentored 4 incoming Sales Development Representatives (SDRs) on discovery frameworks and objection handling.
Sales Development Representative (SDR) | BrightPath Analytics | Chicago, IL
May 2021 – May 2022
* Exceeded monthly SQL quota for 11 consecutive months (124% average attainment) via high-volume outbound prospecting.
Education
Bachelor of Business Administration (B.B.A.) in Marketing | University of Illinois Urbana-Champaign | May 2021
Awards & Recognition
* President's Club Winner — Veloce Cloud Software (2025)"""),
    ("software", """Alex Kim
Software Engineer
Summary
Backend engineer with 4 years building APIs and microservices.
Skills
Python, Go, PostgreSQL, Redis, Docker, Kubernetes, React, TypeScript, Git, CI/CD
Experience
Software Engineer II | Northwind Data | 2022 - Present
- Built REST APIs and microservices in Go serving 3M requests a day
- Led code reviews and wrote unit tests; owned the system design for billing
Software Engineer | Contoso | 2020 - 2022
- Shipped React and Node.js features for the web application
Education
B.S. Computer Science, State University, 2020"""),
    ("ai / ml", """Priya Shah - Machine Learning Engineer
Summary
ML engineer focused on LLMs, retrieval augmented generation and model training.
Experience
Machine Learning Engineer | Fabrikam AI | 2023 - Present
- Fine-tuned transformer models in PyTorch; built RAG pipelines with embeddings and vector search
- Shipped MLOps for inference at scale; evaluation of large language model outputs
Data Scientist | Tailspin | 2021 - 2023
- Built regression and classification models with scikit-learn and pandas
Skills
PyTorch, TensorFlow, Hugging Face, Python, SQL, deep learning, computer vision"""),
    ("data", """Sam Lee
Data Analyst
Experience
Data Analyst | Wide World Importers | 2021 - Present
- Built Tableau and Power BI dashboards on Snowflake; wrote SQL and dbt models
- Ran A/B testing analysis and regression with pandas; data visualization for leadership
Business Analyst | Litware | 2019 - 2021
- ETL with Airflow into the data warehouse
Skills
SQL, Python, Tableau, Looker, statistics, Excel"""),
    ("devops / sre", """Morgan Diaz
Site Reliability Engineer
Experience
Site Reliability Engineer | Adatum Cloud | 2021 - Present
- Ran Kubernetes clusters on AWS with Terraform and Helm; on-call and incident response
- Built observability with Prometheus and Grafana; raised uptime to 99.99% against the SLA
DevOps Engineer | Proseware | 2018 - 2021
- Jenkins and GitHub Actions pipelines; Ansible; Linux administration
Skills
AWS, GCP, Docker, Terraform, Kubernetes, infrastructure as code, monitoring"""),
    ("security", """Chris Park
Security Analyst
Experience
SOC Analyst | Woodgrove Bank | 2022 - Present
- Triage SIEM alerts, incident handling, malware analysis and forensics
- Vulnerability management with OWASP and NIST frameworks; zero trust IAM reviews
Information Security Analyst | Fourth Coffee | 2020 - 2022
- Firewall rules, penetration testing support, encryption standards
Certifications
CISSP, Security+"""),
    ("hardware / embedded", """Dana Ruiz
Firmware Engineer
Experience
Embedded Software Engineer | Lucerne Devices | 2021 - Present
- Wrote C firmware on ARM Cortex microcontrollers with an RTOS; I2C, SPI and UART drivers
- Board bring-up with an oscilloscope; reviewed schematics and PCB layouts in Altium
Hardware Engineer | Trey Research | 2019 - 2021
- FPGA designs in Verilog; UVM verification
Skills
C, C++, embedded, firmware, FPGA, Verilog, signal processing"""),
    ("product", """Jamie Fox
Senior Product Manager
Summary
Product manager with 6 years owning roadmaps for B2B software platforms.
Experience
Senior Product Manager | Blue Yonder Software | 2021 - Present
- Owned the product roadmap and product strategy; wrote PRDs and user stories for engineering
- Ran user research and product discovery; launched pricing go-to-market with sales and marketing
Product Owner | Margie's Travel | 2018 - 2021
- Prioritized the backlog, defined OKRs, tracked product analytics in Mixpanel and Amplitude"""),
    ("design", """Robin Gray
Product Designer
Experience
Product Designer | Humongous Software | 2021 - Present
- Designed user flows, wireframes and prototypes in Figma; built and maintained the design system
- Ran usability testing and journey maps; accessibility reviews for the web app
UX Designer | Coho Vineyard | 2019 - 2021
- Visual design and typography for marketing pages; Photoshop and Illustrator
Skills
Figma, Sketch, prototyping, user interface, interaction design"""),
    ("program / project", """Taylor Brooks
Technical Program Manager
Experience
Technical Program Manager | Northwind Software | 2020 - Present
- Ran cross-functional programs across 6 engineering teams; milestones, dependencies and risk register
- Sprint planning, Jira, status reports to executives; agile and scrum delivery
Project Manager | Contoso Construction | 2016 - 2020
- Scope, budget tracking and Gantt schedules for $12M projects
Certifications
PMP (Project Management Professional)"""),
    ("solutions / sales engineering", """Jesse Wong
Solutions Engineer
Experience
Solutions Engineer | Fabrikam Software | 2021 - Present
- Ran technical discovery and technical demos for enterprise prospects; built proofs of concept
- Answered RFPs and owned pre-sales solution design with account executives
Sales Engineer | Litware | 2019 - 2021
- Customer deployments and customer integrations for API products"""),
    ("marketing", """Casey Hall
Marketing Manager
Experience
Marketing Manager | Proseware Software | 2021 - Present
- Ran demand generation campaigns, SEO and paid search; grew conversion rate 30%
- Email marketing in Marketo and HubSpot; brand strategy, positioning and messaging
Content Marketer | Adventure Works | 2018 - 2021
- Copywriting, social media and content marketing; Google Analytics reporting"""),
    ("customer success / support", """Avery Cole
Customer Success Manager
Experience
Customer Success Manager | Adatum Software | 2021 - Present
- Owned renewals for 60 accounts; net revenue retention 112%; reduced churn
- Ran customer onboarding and quarterly health reviews; NPS and CSAT programs in Zendesk
Customer Support Specialist | Tailwind Traders | 2019 - 2021
- Resolved tickets and escalations; wrote the knowledge base"""),
    ("finance / accounting", """Jordan Lee
Staff Accountant
Experience
Senior Accountant | Cloud Software Inc | 2022 - Present
- Month-end close, journal entries, accruals and account reconciliations under US GAAP
- Prepared financial statements and variance analysis; SOX controls; NetSuite
Staff Accountant | Contoso Ltd | 2019 - 2022
- General ledger, accounts payable and audit support in QuickBooks
Certifications
CPA"""),
    ("healthcare", """Maria Lopez, RN
Registered Nurse
Experience
Registered Nurse, ICU | Mercy General Hospital | 2020 - Present
- Patient care for 2-3 critical patients; medication administration and vital signs
- Charted in Epic EHR; triage and care plans with physicians
Certified Nursing Assistant | Sunrise Care | 2018 - 2020
- Bedside care and patient mobility
Licenses
RN license, BLS, ACLS"""),
    ("education", """Kim Nguyen
High School Teacher
Experience
Math Teacher | Lincoln High School | 2017 - Present
- Wrote lesson plans and curriculum for 150 students; classroom management and grading
- Differentiated instruction and IEP support; raised standardized test scores 12%
Tutor | Learning Center | 2015 - 2017
Education
M.Ed. Curriculum and Instruction"""),
    ("legal", """Pat Rivera
Attorney
Experience
Associate Attorney | Smith & Cole LLP | 2019 - Present
- Litigation and contract drafting; legal research on Westlaw and LexisNexis
- Took depositions, drafted briefs and court filings; due diligence for M&A
Law Clerk | Superior Court | 2018 - 2019
Education
Juris Doctor, State Law School; Bar admission, California"""),
    ("people / hr", """Riley Adams
Technical Recruiter
Summary
Technical recruiter who hires software engineers, data scientists and machine learning engineers.
Experience
Technical Recruiter | Northwind Software | 2021 - Present
- Full-cycle recruiting for 40 software engineer and backend engineer roles a year
- Sourcing on LinkedIn, interview loops with hiring managers, offer letters in Greenhouse
Talent Acquisition Partner | Contoso | 2019 - 2021
- Built talent pipelines and the employer brand; headcount planning"""),
    ("operations / supply chain", """Drew Morgan
Supply Chain Analyst
Experience
Supply Chain Analyst | Wide World Importers | 2020 - Present
- Demand planning and inventory optimization in SAP ERP; vendor management and purchase orders
- Lean and Six Sigma process improvement in the distribution center
Logistics Coordinator | Tailspin Toys | 2018 - 2020
- Shipping and fulfillment scheduling"""),
    ("administrative", """Lee Carter
Executive Assistant
Experience
Executive Assistant | Fabrikam Software | 2020 - Present
- Calendar management and scheduling for the CEO; travel arrangements and expense reports
- Meeting minutes, correspondence and office supplies; Microsoft Office
Receptionist | Coho Dental | 2017 - 2020
- Front desk, phone support and data entry"""),
    ("research / science", """Sky Patel
Research Associate
Experience
Research Associate | Institute of Biology | 2021 - Present
- Cell culture, PCR, Western blot and assays for a peer-reviewed publication
- Designed experiments and tested hypotheses; spectroscopy and chromatography
Laboratory Technician | University Lab | 2019 - 2021
Education
B.S. Biology; thesis on microbial specimens"""),
    ("engineering (non-software)", """Quinn Baker
Mechanical Engineer
Experience
Mechanical Engineer | Contoso Manufacturing | 2019 - Present
- Designed parts in SolidWorks and AutoCAD with GD&T and tolerance stack-ups
- Finite element analysis in ANSYS; root cause analysis and quality control under ISO 9001
Manufacturing Engineer | Trey Industries | 2017 - 2019"""),
    ("skilled trades", """Bo Martinez
Journeyman Electrician
Experience
Electrician | City Electric | 2016 - Present
- Residential and commercial wiring from blueprints; installation and troubleshooting
- OSHA safety compliance; preventive maintenance; power tools and hand tools
Apprentice Electrician | Bright Power | 2012 - 2016
Certifications
Journeyman license, OSHA 30"""),
    ("hospitality / retail", """Jo Evans
Shift Supervisor
Experience
Shift Supervisor | Corner Cafe | 2021 - Present
- Ran the floor, cash handling and point of sale; food safety and ServSafe
- Trained new baristas; inventory counts and guest experience
Barista | Bean House | 2019 - 2021
- Food preparation and customer service"""),
    ("creative / media", """Ellis Grant
Journalist and Editor
Experience
Senior Editor | City Daily News | 2019 - Present
- Edited 20 stories a week in AP style; editorial planning and proofreading
- Wrote bylines on local politics; produced a weekly podcast
Reporter | Valley Times | 2016 - 2019
- Storytelling, photography and videography for features"""),
    ("software", """Jordan Reyes
Software Engineer
Experience
Software Engineer | Startup Labs | 2023 - Present
- Built React and TypeScript features and REST APIs in Node.js; unit tests and code reviews
Math Teacher | Lincoln High School | 2014 - 2022
- Lesson plans, curriculum and classroom management for 150 students
Education
Coding bootcamp, full-stack web development"""),
    ("software", """Ana Silva
Computer Science student, graduating May 2026
Education
B.S. Computer Science, State University, expected 2026
Coursework: data structures, algorithms, operating systems
Projects
Campus Rides | React, Node.js, PostgreSQL
- Built a full-stack web application with REST APIs
Compiler | C++
- Wrote a parser and code generator in C++ with unit tests
Skills
Java, Python, JavaScript, Git"""),
    ("healthcare", "Maria Gomez Registered Nurse • Summary • Compassionate RN with 6 years of patient care in med-surg and telemetry units. • Experience • Registered Nurse | Valley Hospital | 2019 - Present • Medication administration, vital signs, care plans, Epic EHR charting • Licenses • RN, BLS, ACLS"),
    ("software", """Lee Zhang
Backend developer, 5 years
Senior Software Engineer at Contoso Payments, 2021 - Present
Built Java Spring Boot microservices and REST APIs on Kubernetes
Software Developer at Litware, 2019 - 2021
Wrote Python Django services and unit tests"""),
    ("unclassified", "Hello world. This is a test of the thing. Lorem ipsum dolor sit amet."),
]

# posting titles -> the family each must land in
TITLES = [
    ("Senior Software Engineer, Backend", "software"), ("Principal Software Engineer", "software"),
    ("Enterprise Account Executive", "sales"), ("Sales Development Representative", "sales"),
    ("Registered Nurse - ICU", "healthcare"), ("Staff Accountant", "finance / accounting"),
    ("Machine Learning Engineer", "ai / ml"), ("Sales Engineer", "solutions / sales engineering"),
    ("Product Designer", "design"), ("Technical Recruiter", "people / hr"), ("Data Scientist II", "data"),
    ("Site Reliability Engineer", "devops / sre"), ("Customer Success Manager", "customer success / support"),
    ("Product Marketing Manager", "marketing"), ("Senior Product Manager, Payments", "product"),
    ("Firmware Engineer", "hardware / embedded"), ("Executive Assistant to the CEO", "administrative"),
    ("Mechanical Engineer", "engineering (non-software)"), ("Paralegal", "legal"), ("High School Teacher", "education"),
]

# titles that name no full role (the CUES back-off path); used to check the web port gives the same families
PARITY_TITLES = ["Director, Sales Development, Japan", "Senior GRC Engineer", "Manager, Strategic Finance",
                 "Head of Creative Operations", "Marketing Analytics Lead, Enterprise Marketing", "Senior Manager, Engineering",
                 "Legal Operations Specialist", "Retail Partner Manager", "Research Engineer, Life Sciences",
                 "Director, Product Design - AI & Context", "People Services Partner, Compliance", "Repair Coordinator",
                 "Senior Business Systems Analyst", "Manager, Ocean Freight", "Customer Experience Lead, EMEA", "Subject Matter Expert"]
