"""Held-out benchmark for the resume classifier (engine/resume_nlp.py): resumes NOT used to tune it.

tests/resume_corpus.py is the development set the vocabulary was tuned on; this file is written separately, in other
styles (other header names, "@" role lines, lowercase, terse, one-line pastes), so scripts/resume_bench.py can report
honest accuracy, precision, recall, F1 and a confusion matrix. All people and companies are fictional. When a miss here
is fixed, the fix must be general (vocabulary or structure), never a rule written for one benchmark resume, and the
report records the score before and after.
"""

BENCH = [
    # --- software
    ("software", """MARCUS OYELARAN
Full Stack Developer
WORK HISTORY
Full Stack Developer @ Pixelforge (2021 – now)
• Next.js + TypeScript front end, GraphQL gateway, Postgres
• Cut page load 45%; wrote Jest unit tests and ran code review for 5 devs
Junior Web Developer @ Brightline Media (2019 – 2021)
• PHP and Laravel sites, MySQL, Git
EDUCATION
BSc Software Engineering"""),
    ("software", """sofia marquez · android engineer · lisbon
experience
android engineer, mobilely — 2022–present
kotlin, jetpack compose, rest api clients, ci/cd with github actions
ios developer, appnest — 2020–2022
swift, swiftui, mobile app releases to 1m users"""),
    ("software", "Ken Ito — Backend Developer. Professional Experience: Backend Developer | Shiprocket | 2020 - Present. Java, Spring Boot microservices, Kafka, REST APIs, system design reviews. Junior Developer | Codeworks | 2018 - 2020. C# and .NET web application maintenance."),
    # --- ai / ml
    ("ai / ml", """Dr. Lena Fischer
Applied Scientist
Research & Industry Experience
Applied Scientist | Voxa Labs | 2022 - present
- Trained transformer-based speech models; reinforcement learning from human feedback
- Deployed inference services; neural network distillation in PyTorch
PhD, Machine Learning, 2022 — thesis on deep learning for audio"""),
    ("ai / ml", """Omar Haddad | AI Engineer
Experience
AI Engineer, Helix Health (2023-Present): built LLM agents and retrieval augmented generation over clinical notes; embeddings, vector search, fine tuning with Hugging Face
Computer Vision Engineer, Optix (2020-2023): object detection in TensorFlow; model training pipelines; generative AI prototypes"""),
    # --- data
    ("data", """GRACE OKAFOR
Data Engineer
Professional Experience
Data Engineer — Rivermark Bank — 2021-Present
* Spark and Airflow pipelines into BigQuery; dbt data models; Kafka streams
* Owned the data warehouse and SLAs for 200 dashboards
Analytics Engineer — Ledgerly — 2019-2021
* SQL, Looker, ETL"""),
    ("data", """Victor Lindqvist, Data Scientist
Experience
Data Scientist, Northpeak Retail, 2020–present: regression and churn statistics in Python and R; A/B testing; Tableau dashboards
Quantitative Analyst, Fjord Capital, 2017–2020: statistical models, SQL"""),
    # --- devops / sre
    ("devops / sre", """Hana Novak
Cloud Engineer
Experience
Cloud Engineer | Stratus Systems | 2021 - Present
- Azure and AWS landing zones in Terraform; Kubernetes with Helm; Prometheus alerting
System Administrator | Cityline ISP | 2017 - 2021
- Linux servers, networking, load balancers, backups, on-call"""),
    ("devops / sre", "Raj Iyer. Infrastructure Engineer at Kestrel (2019-now): infrastructure as code with Ansible and Terraform, Docker, Jenkins, GCP, observability with Grafana, incident response and uptime for 300 services."),
    # --- security
    ("security", """Elena Petrova
Penetration Tester
Experience
Penetration Tester | RedShield Consulting | 2021 - Present
- External and internal penetration testing, red team engagements, OWASP top 10 web testing
- Threat models and vulnerability reports for 40 clients
Security Engineer | Paysafe Labs | 2018 - 2021
- AppSec reviews, IAM hardening, encryption key management
Certifications: OSCP, CISSP"""),
    ("security", """Tom Becker — Cybersecurity Analyst
WORK
Cybersecurity Analyst, Statewide Credit Union (2020-present)
SIEM tuning, SOC triage, malware forensics, NIST and ISO 27001 audits, firewall changes, zero trust rollout"""),
    # --- hardware / embedded
    ("hardware / embedded", """Mei Lin
FPGA Engineer
Experience
FPGA Engineer | Quantix Instruments | 2020 - Present
- RTL in VHDL and Verilog for signal processing; timing closure; UVM testbenches
Validation Engineer | Coreway Semiconductor | 2017 - 2020
- Silicon bring-up with oscilloscopes and logic analyzers; ASIC validation"""),
    ("hardware / embedded", "Diego Alvarez — Electrical Engineer. Experience: Electrical Engineer, Voltis Robotics, 2019-present: PCB design in Altium, schematic capture, microcontroller firmware in C over SPI and I2C, circuit debugging."),
    # --- product
    ("product", """Nadia Rahman
Group Product Manager
Experience
Group Product Manager | Cartwheel Commerce | 2021 - Present
- Led 4 product managers; product vision and roadmap for checkout; OKRs
- Product discovery with user research; product launches with go-to-market partners
Associate Product Manager | Tradewind | 2018 - 2021
- PRDs, backlog grooming, feature prioritization, Amplitude funnels"""),
    ("product", "Ben Carter — Technical Product Manager at Gridline (2020-2025): owned the API platform roadmap, wrote product requirements, ran market research and product analytics; Product Owner at Nimbus (2017-2020): user stories and backlog."),
    # --- design
    ("design", """Aiko Tanaka
UX Researcher & Designer
Experience
UX Researcher | Bloomly | 2021 - Present
- Usability testing with 80 participants; personas and journey maps; findings drove the redesign
Interaction Designer | Kite Studio | 2018 - 2021
- Wireframes, prototypes and user flows in Figma and Sketch; accessibility audits"""),
    ("design", """Lucas Moreau — Graphic Designer
Experience: Graphic Designer, Atelier Nord, 2019-present — brand identities, typography, visual design in Adobe Illustrator, Photoshop and InDesign; Motion Designer, Reelcraft, 2017-2019 — After Effects animations."""),
    # --- program / project
    ("program / project", """Fatima Zahra
Project Manager, PMP
Experience
Project Manager | Meridian Construction | 2018 - Present
- Managed scope, budget tracking and milestones for $40M builds; Gantt schedules and risk register
- Weekly status reports to stakeholders; waterfall delivery
Project Coordinator | Atlas Engineering | 2015 - 2018"""),
    ("program / project", "Owen Price — Scrum Master. Scrum Master at Finch Software (2021-present): sprint planning, kanban boards in Jira, agile coaching for 3 teams, dependency tracking; Delivery Manager at Orbit (2018-2021): cross-functional program management."),
    # --- solutions / sales engineering
    ("solutions / sales engineering", """Isabel Cruz
Solutions Architect
Experience
Solutions Architect | Cloudreach Partners | 2020 - Present
- Pre-sales solution design and proofs of concept for enterprise customers; RFP responses
- Technical demos with account executives; customer integrations on AWS
Implementation Engineer | Dataloom | 2017 - 2020"""),
    ("solutions / sales engineering", "Peter Novak — Forward Deployed Engineer at Palisade AI (2022-present): customer deployments, technical discovery and proof of concept builds on site; Customer Engineer at Streamly (2019-2022)."),
    # --- sales
    ("sales", """Brianna Cole
Business Development Representative
Experience
BDR | Fluxon Software | 2023 - Present
- 60 cold calls a day; booked 25 meetings a month; 130% of quota
- Outbound sequences in Outreach and Salesforce; lead generation for 3 AEs
Retail Sales Associate | Nordline | 2021 - 2023"""),
    ("sales", """Michael Grant — Regional Sales Manager
Experience
Regional Sales Manager, Medivance Devices (2018–present): led 8 sales representatives across 5 states, $14M book of business, territory planning, negotiation with hospital buyers, commission plans
Territory Manager, Ortholine (2014–2018): grew territory revenue 40%"""),
    ("sales", "Lauren Price — Enterprise Account Executive. Account Executive at Clarion Cloud (2021-present): closed $2.3M in ARR, full cycle sales, MEDDIC, president's club 2023; Sales Development Representative at Clarion Cloud (2019-2021)."),
    # --- marketing
    ("marketing", """Chloe Martin
Product Marketing Manager
Experience
Product Marketing Manager | Lattice HR Software | 2021 - Present
- Positioning and messaging for 3 launches; sales enablement; competitive campaigns
Digital Marketing Manager | Bloom Brands | 2018 - 2021
- Paid social and paid search budgets of $2M; SEO; email marketing in Marketo"""),
    ("marketing", "Arjun Mehta — Growth Marketer. Growth Marketer at Snapcart (2022-present): demand generation, conversion rate optimization, CAC and CTR reporting in Google Analytics, influencer campaigns; Social Media Manager at Zesty (2019-2022)."),
    # --- customer success / support
    ("customer success / support", """Nora Jensen
Technical Support Engineer
Experience
Technical Support Engineer | Helpwise Software | 2021 - Present
- Resolved 40 tickets a day; escalations to engineering; wrote knowledge base articles in Zendesk
Customer Service Representative | Telco One | 2018 - 2021
- Call center support; CSAT 96%"""),
    ("customer success / support", "Paulo Ramos — Customer Success Manager at Brightdesk (2020-present): renewals and expansions, churn reduction, customer onboarding, NPS programs, customer health scores in Gainsight; Onboarding Specialist at Brightdesk (2018-2020)."),
    # --- finance / accounting
    ("finance / accounting", """Hannah Wright, CPA
Senior Financial Analyst
Experience
Senior Financial Analyst | Corvid Software | 2021 - Present
- FP&A: budgeting, forecasting, variance analysis and the 3-statement financial model
Auditor | Price & Lowe LLP | 2017 - 2021
- External audit under GAAP and IFRS; SOX testing"""),
    ("finance / accounting", "Ahmed Saleh — Bookkeeper. Bookkeeper at Greenleaf Bakery (2019-present): accounts payable and receivable, reconciliations in QuickBooks, payroll journal entries, month-end close; Tax Associate at H&R Partners (2016-2019): tax returns."),
    # --- healthcare
    ("healthcare", """Grace Mwangi
Physical Therapist, DPT
Experience
Physical Therapist | Summit Rehab Clinic | 2019 - Present
- Evaluation, diagnosis and treatment plans for 14 patients a day; orthopedic and sports rehabilitation
Physical Therapy Aide | City Hospital | 2016 - 2019
Licenses: PT license, CPR"""),
    ("healthcare", "Jose Ramirez — Paramedic / EMT. Paramedic at County EMS (2018-present): emergency patient care, triage, ACLS, medication administration in the field; Emergency Medical Technician at Metro Ambulance (2015-2018); BLS instructor."),
    ("healthcare", """Dr. Anita Rao
Physician (Internal Medicine)
Clinical Experience
Attending Physician | St. Mary's Hospital | 2017 - Present
- Inpatient diagnosis and treatment; EHR documentation in Epic; supervised residents
Board certified, Internal Medicine"""),
    # --- education
    ("education", """Samuel Brooks
Elementary Teacher
Teaching Experience
Third Grade Teacher | Oakwood Elementary | 2016 - Present
- Classroom of 26; lesson plans aligned to state standards; differentiated instruction
- Parent-teacher conferences; IEP meetings with the special education team
Substitute Teacher | District 9 | 2014 - 2016"""),
    ("education", "Prof. Helen Clarke — Professor of History, Westbrook University (2010-present): lectures to 200 students, syllabus and curriculum design, pedagogy research; Lecturer, Eastfield College (2005-2010)."),
    # --- legal
    ("legal", """Monica Chen
Paralegal
Experience
Paralegal | Hart & Vale LLP | 2019 - Present
- Case management for 60 litigation matters; court filings and discovery motions
- Legal research on Westlaw; drafted deposition summaries
Legal Assistant | City Law Group | 2016 - 2019"""),
    ("legal", "Daniel Okoro — Corporate Counsel at Brightway Inc (2018-present): contract drafting and negotiation, regulatory compliance, intellectual property, due diligence; Associate Attorney at Mills Law (2014-2018); Juris Doctor; bar admission New York."),
    # --- people / hr
    ("people / hr", """Sara Lindgren
HR Business Partner
Experience
HR Business Partner | Northgate Manufacturing | 2019 - Present
- Employee relations, performance reviews and workforce planning for 600 employees
- Benefits administration and payroll changes in Workday HRIS
HR Generalist | Valley Foods | 2015 - 2019"""),
    ("people / hr", "Kevin Doyle — Sourcer. Sourcer at Talentbridge (2022-present): sourcing engineers and nurses, candidate outreach, talent pipeline building in the applicant tracking system, scheduling interview loops with hiring managers."),
    # --- operations / supply chain
    ("operations / supply chain", """Linda Park
Operations Manager
Experience
Operations Manager | Swiftship Logistics | 2018 - Present
- Ran a 200-person distribution center; warehouse KPIs, shipping and fulfillment
- Lean process improvement cut cost per order 18%; vendor management
Inventory Analyst | Freshmart | 2015 - 2018"""),
    ("operations / supply chain", "Marco Bianchi — Procurement Specialist at Alpina Foods (2019-present): sourcing strategy, purchase orders in SAP ERP, supplier negotiation; Buyer at Tessera Retail (2016-2019): demand planning and inventory."),
    # --- administrative
    ("administrative", """Patricia Hall
Office Manager
Experience
Office Manager | Greenfield Dental | 2018 - Present
- Front office, scheduling for 4 dentists, office supplies, expense reports
Administrative Assistant | Pinecrest Realty | 2014 - 2018
- Data entry, filing, correspondence, calendar management, Microsoft Office"""),
    ("administrative", "Yusuf Demir — Executive Assistant to the CFO at Corvex (2020-present): calendar management, travel arrangements, meeting minutes, board materials; Receptionist at Harbor Hotel (2017-2020)."),
    # --- research / science
    ("research / science", """Dr. Pierre Laurent
Postdoctoral Researcher, Chemistry
Research Experience
Postdoctoral Researcher | National Lab | 2021 - Present
- Synthesis and spectroscopy of catalysts; 9 peer-reviewed publications; grant writing
PhD Chemistry | Université de Lyon | 2021 — dissertation on chromatography methods"""),
    ("research / science", "Amara Diallo — Environmental Scientist at EcoSurvey (2019-present): field research, water specimens, laboratory assays, environmental reports; Research Assistant at State University (2017-2019): experiments and hypothesis testing."),
    # --- engineering (non-software)
    ("engineering (non-software)", """Rafael Souza
Civil Engineer, PE
Experience
Civil Engineer | Bridgeline Infrastructure | 2017 - Present
- Structural analysis and design of highway bridges; AutoCAD Civil 3D; construction oversight
Project Engineer | Terra Builders | 2014 - 2017"""),
    ("engineering (non-software)", "Ingrid Holm — Process Engineer at Nordic Chemicals (2018-present): process optimization, root cause analysis, quality control, six sigma, ISO 9001 audits, thermodynamics and fluid modeling in MATLAB."),
    # --- skilled trades
    ("skilled trades", """Carlos Mendez
Welder / Fabricator
Experience
Welder | Steelworks Fabrication | 2015 - Present
- MIG and TIG welding from blueprints; OSHA safety compliance; power tools
Apprentice Welder | Ironside Shop | 2012 - 2015
Certifications: AWS certified welder"""),
    ("skilled trades", "Dale Robinson — HVAC Technician at CoolAir Services (2016-present): installation and preventive maintenance of HVAC systems, troubleshooting equipment, wiring; CDL Class A truck driver (2010-2016)."),
    # --- hospitality / retail
    ("hospitality / retail", """Emma Wilson
Restaurant Manager
Experience
Restaurant Manager | The Olive Table | 2019 - Present
- Ran front and back of house for 40 staff; menu costing, food safety, reservations
Server | Harbor Grill | 2016 - 2019
- Guest experience, cash handling, point of sale"""),
    ("hospitality / retail", "Liam Murphy — Store Manager at Urban Outfit (2020-present): store operations, visual merchandising, inventory counts, scheduling 25 associates; Cashier and Sales Floor Associate (2017-2020)."),
    # --- creative / media
    ("creative / media", """Zoe Adams
Technical Writer
Experience
Technical Writer | Cloudnine Software | 2020 - Present
- User guides and API reference docs; editorial style guide; proofreading release notes
Copywriter | Inkwell Agency | 2017 - 2020
- Copy for campaigns; storytelling"""),
    ("creative / media", "Andre Silva — Video Editor & Producer. Video Editor at Northstar Films (2019-present): editing in Adobe Premiere and Final Cut, videography, color; Producer of a weekly podcast (2018-present)."),
    # --- hybrids and traps (the label is the primary one: what the person does now)
    ("sales", """Ravi Kumar
Account Manager
Experience
Account Manager | Datacore Software | 2021 - Present
- Managed a $6M book of business of software customers; upsell and cross-sell; quota 115%
Software Engineer | Datacore Software | 2017 - 2021
- Java microservices and REST APIs"""),
    ("data", """Julia Novak
Data Analyst (formerly Registered Nurse)
Experience
Data Analyst | Carepath Health | 2023 - Present
- SQL and Tableau dashboards on patient outcomes; Python statistics
Registered Nurse | City Hospital | 2015 - 2022
- Patient care, medication administration"""),
    ("people / hr", """Mia Torres
Recruiter
Experience
Recruiter | Healthbridge Staffing | 2020 - Present
- Recruiting registered nurses, physical therapists and pharmacists for hospitals; offer letters
- Candidate sourcing and interview scheduling with hiring managers"""),
    ("finance / accounting", """Noah Fischer
Controller
Experience
Controller | Lumen Software | 2019 - Present
- Owned the general ledger, month-end close, audit and tax for a SaaS company; GAAP revenue recognition
Senior Accountant | Brightside | 2015 - 2019"""),
    ("education", """Isla Brown
Instructional Designer
Experience
Instructional Designer | Learnwell | 2020 - Present
- Curriculum and learning objectives for online courses; lesson plans; teaching with LMS
Teacher | Riverside Middle School | 2014 - 2020"""),
    ("software", """Hyun Woo Park
Game Developer
Experience
Game Developer | Starforge Studios | 2020 - Present
- C++ gameplay systems and tools; algorithm and data structure work for physics
Junior Programmer | Pixel Bay | 2018 - 2020"""),
    ("healthcare", "Pharmacist with 8 years in retail and hospital pharmacy: medication reviews, patient counseling, HIPAA compliance, inventory of controlled substances. Pharmacist, CareRx 2017-present; Pharmacy Technician, CareRx 2014-2017."),
    # --- not a resume / too little evidence
    ("unclassified", "Looking for a job. Hard worker, team player, fast learner. Available immediately."),
    ("unclassified", "Curriculum vitae\nName: J. Doe\nPhone: 555-0100\nEmail: jdoe@example.com"),
    ("unclassified", "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs."),
]
