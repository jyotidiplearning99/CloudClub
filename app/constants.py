"""
Centralized taxonomies from:
- Salesforce Product List for CC.xlsx (v3.2)
- Cloud_Club_Skills_Taxonomy.xlsx (v3.4)
"""

# ============================================================================
# VENDOR DETECTION
# ============================================================================

KNOWN_VENDOR_NAMES = {
    "accenture", "deloitte", "capgemini", "cognizant", "infosys", "wipro", 
    "tcs", "tata consultancy", "hcl", "tech mahindra",
    "ntt data", "ewave", "dvlpr", "osf digital", "osf global", "cloudnerd", 
    "genisis", "relevantz", "guerratech",
    "teksystems", "tek systems", "v-soft", "vsoft", "v-soft consulting",
    "zensar", "zensar technologies", "quinnox", "fortech",
    "kcsit", "machinas", "soitron", "wunderman", "globant",
    "sysmap", "consulting", "consultancy", "staffing", "solutions inc",
    "zscaler"
}

VENDOR_INDICATORS = [
    "consulting", "consultancy", "staffing", "solutions", "services",
    "technologies", "technology", "tech", "global services"
]


# ============================================================================
# SALESFORCE PRODUCTS (from Salesforce Product List for CC.xlsx)
# 64 products total
# ============================================================================

SALESFORCE_PRODUCTS_CANONICAL = {
    # Core Clouds
    "Sales Cloud",
    "Service Cloud", 
    "Experience Cloud",
    "Field Service",
    "Marketing Cloud",
    
    # Marketing Cloud Modules
    "Marketing Cloud Account Engagement",  # Pardot
    "Marketing Cloud Intelligence",  # Datorama
    "Marketing Cloud Advertising",
    "Marketing Cloud Personalization",
    
    # Revenue Cloud Family
    "Revenue Cloud",
    "CPQ",
    "CPQ Billing",
    "Revenue Intelligence",
    
    # Industry Clouds
    "Financial Services Cloud",
    "Health Cloud",
    "Manufacturing Cloud",
    "Nonprofit Cloud",
    "Education Cloud",
    "Automotive Cloud",
    "Consumer Goods Cloud",
    "Energy & Utilities Cloud",
    "Media Cloud",
    "Pharma Cloud",
    "Public Sector Cloud",
    
    # Analytics
    "CRM Analytics",  # Tableau CRM
    "Tableau",
    "Einstein Discovery",
    "Data Cloud",
    
    # Integration
    "MuleSoft Anypoint Platform",
    "Heroku Platform",
    
    # AI & Automation
    "Einstein AI",
    "Agentforce",
    "Einstein Conversation Insights",
    "Einstein Sales Intelligence",
    "Prompt Builder",
    "Einstein Bots",
    
    # Commerce
    "Commerce Cloud",
    "Commerce Cloud B2B",
    "Commerce Cloud B2C",
    "Order Management",
    
    # Add-ons
    "Loyalty Management",
    "Net Zero Cloud",
    "Slack for Salesforce",
    "Safety Cloud",
    "Agentforce Copilot Studio",
    "Customer Community",
    "Employee Community",
    "Partner Community",
    "Data Pipelines",
    "External Services & OpenAPI",
    "Identity",
    "Platform Events",
    "Sales Engagement",
    "Salesforce Flow",
    "Salesforce Industries",
    "Salesforce Platform",
    "Salesforce Shield",
}

# Product aliases (from Excel "Alternative / Abbreviation" column)
PRODUCT_ALIASES = {
    # Sales Cloud
    "sales": "Sales Cloud",
    "sfc": "Sales Cloud",
    "sales cloud": "Sales Cloud",
    
    # Service Cloud
    "service": "Service Cloud",
    "sc": "Service Cloud",
    "service cloud": "Service Cloud",
    
    # Experience Cloud
    "expc": "Experience Cloud",
    "sites": "Experience Cloud",
    "community cloud": "Experience Cloud",
    "communities": "Experience Cloud",
    "community": "Experience Cloud",
    "experience cloud": "Experience Cloud",
    
    # Field Service
    "fsl": "Field Service",
    "sfs": "Field Service",
    "field service lightning": "Field Service",
    "field service": "Field Service",
    
    # Marketing Cloud
    "sfmc": "Marketing Cloud",
    "mce": "Marketing Cloud",
    "exacttarget": "Marketing Cloud",
    "marketing cloud engagement": "Marketing Cloud",
    "marketing cloud": "Marketing Cloud",
    
    # Pardot
    "mcae": "Marketing Cloud Account Engagement",
    "pardot": "Marketing Cloud Account Engagement",
    "marketing cloud account engagement": "Marketing Cloud Account Engagement",
    
    # Datorama
    "mci": "Marketing Cloud Intelligence",
    "datorama": "Marketing Cloud Intelligence",
    "marketing cloud intelligence": "Marketing Cloud Intelligence",
    
    # CPQ
    "cpq": "CPQ",
    "configure price quote": "CPQ",
    "steelbrick cpq": "CPQ",
    "salesforce cpq": "CPQ",
    
    # Billing
    "billing": "CPQ Billing",
    "steelbrick billing": "CPQ Billing",
    
    # Financial Services Cloud
    "fsc": "Financial Services Cloud",
    "financial services cloud": "Financial Services Cloud",
    
    # Health Cloud
    "hc": "Health Cloud",
    "health cloud": "Health Cloud",
    
    # CRM Analytics
    "crma": "CRM Analytics",
    "tableau crm": "CRM Analytics",
    "einstein analytics": "CRM Analytics",
    "wave": "CRM Analytics",
    "wave analytics": "CRM Analytics",
    
    # Tableau
    "tableau bi": "Tableau",
    "tableau": "Tableau",
    
    # Data Cloud
    "dc": "Data Cloud",
    "genie": "Data Cloud",
    "customer data platform": "Data Cloud",
    "cdp": "Data Cloud",
    "data cloud": "Data Cloud",
    
    # MuleSoft
    "mulesoft": "MuleSoft Anypoint Platform",
    "anypoint": "MuleSoft Anypoint Platform",
    
    # Einstein AI
    "einstein": "Einstein AI",
    "copilot": "Einstein AI",
    
    # Commerce Cloud
    "cc": "Commerce Cloud",
    "commerce cloud": "Commerce Cloud",
    "b2b commerce": "Commerce Cloud B2B",
    "b2c commerce": "Commerce Cloud B2C",
    "sfcc": "Commerce Cloud B2C",
    "demandware": "Commerce Cloud B2C",
    "cloudcraze": "Commerce Cloud B2B",

    "Agentforce Copilot Studio": "Agentforce Copilot Studio",
    "Customer Community" : "Customer Community",
    "Employee Community":"Employee Community",
    "Partner Community": "Partner Community",

    "Data Pipelines":"Data Pipelines",
    "External Services & OpenAPI":"External Services & OpenAPI",
    "Identity":"Identity",
    "Platform Events":"Platform Events",

    "Sales Engagement":"Sales Engagement",
    "Salesforce Flow":"Salesforce Flow",
    "Salesforce Industries":"Salesforce Industries",
    "Salesforce Platform":"Salesforce Platform",
    "Salesforce Shield":"Salesforce Shield",

    "einstein bots": "Einstein AI",
    "heroku": "Salesforce Platform",
    "heroku platform": "Salesforce Platform",
}


# ============================================================================
# SKILLS TAXONOMY (from Cloud_Club_Skills_Taxonomy.xlsx)
# 193 skills across 14 categories
# ============================================================================

SKILLS_CATEGORIES = {
    "admin_and_automation": {
        "name": "Admin & Automation",
        "skills": [
            "Flow Builder", "Record-Triggered Flows", "Screen Flows",
            "Process Builder", "Workflow Rules", "Validation Rules",
            "Reports", "Dashboards", "Data Loader", "Data Import Wizard",
            "Page Layouts", "Record Types", "Profiles", "Permission Sets",
            "Permission Set Groups", "Sharing Rules", "Queues", "Role Hierarchy",
            "Email Templates", "Approval Processes", "Omni-Channel Routing",
            "Knowledge Management", "Case Assignment", "Sandbox Management",
            "User Management"
        ]
    },
    "dev_coding": {
        "name": "Development & Coding",
        "skills": [
            "Apex", "Apex Class", "Apex Trigger", "Test Classes",
            "SOQL", "SOSL", "Lightning Web Components", "LWC",
            "Aura Components", "Visualforce", "API Integration",
            "Batch Apex", "Queueable Apex", "Future Methods",
            "Asynchronous Apex", "Schedulable Apex", "SFDX",
            "Salesforce CLI", "Unlocked Packages", "Git",
            "Version Control", "VS Code", "Code Builder",
            "Static Code Analysis", "Deployment Packaging", "Scratch Orgs",
            "JavaScript", "TypeScript", "Python", "Java", "Node.js",
            "HTML", "CSS", "React", "Angular","C# / .NET", "JSON", "PowerShell", "Shell / Bash", "XML"
        ]
    },
    "architecture_design": {
        "name": "Architecture & Design",
        "skills": [
            "Solution Design", "Pre-Sales", "Discovery", "Stakeholder Management",
            "Data Modeling", "Security Model Design", "Scalability", "Performance",
            "Integration Patterns", "API-Led Architecture",
            "Event-Driven Architecture", "Multi-Org Strategy",
            "Governance", "Standards", "Documentation", "Diagrams",
            "Well-Architected", "Solution Blueprint"
        ]
    },
    "data_management": {
        "name": "Data Management",
        "skills": [
            "Data Migration", "Data Loader", "ETL", "Data Quality",
            "Deduplication", "Data Import Wizard", "Bulk API"
        ]
    },
    "deployment_devops": {
        "name": "Deployment & DevOps",
        "skills": [
            "Copado", "Gearset", "AutoRABIT", "Jenkins", "Azure DevOps",
            "GitHub", "GitLab", "Bitbucket", "SFDX", "Unlocked Packages",
            "ANT Migration Tool", "CI/CD Pipelines", "Source Control",
            "Static Code Analysis", "Backup", "Restore", "Sandbox Strategy",
            "Test Automation"
        ]
    },
    "integration": {
        "name": "Integration",
        "skills": [
            "MuleSoft", "Informatica", "Dell Boomi", "Jitterbit",
            "Workato", "Tray.io", "Zapier", "REST API", "SOAP API",
            "Platform Events", "Change Data Capture", "External Services",
            "Named Credentials", "Webhooks", "Kafka", "AWS Lambda",
            "Azure Functions", "Heroku Connect"
        ]
    },
    "data_reporting": {
        "name": "Data & Reporting",
        "skills": [
            "CRM Analytics",
            "Data Pipelines",
            "Datorama",
            "Einstein Discovery",
            "Excel / Google Sheets",
            "Power BI",
            "Reporting Snapshots",
            "SQL",
            "Salesforce Data Cloud",
            "Tableau",
        ],
    },

    "ecosystem_tools": {
        "name": "Ecosystem Tools & Extensions",
        "skills": [
            "Adobe Sign",
            "Conga CPQ",
            "Conga Composer",
            "DocuSign",
            "Formstack",
            "LinkedIn Sales Navigator",
            "Outreach",
            "OwnBackup",
            "Spanning Backup",
            "SurveyMonkey",
            "Veeva",
            "ZoomInfo",
            "nCino",
        ],
    },

    "security_compliance": {
        "name": "Security & Compliance",
        "skills": [
            "Compliance Frameworks",
            "Data Classification",
            "Encryption",
            "Event Monitoring",
            "Field-Level Security",
            "MFA",
            "OAuth / OpenID Connect",
            "SSO",
            "Salesforce Shield",
            "Transaction Security",
        ],
    },

    "delivery_methodology": {
        "name": "Delivery & Methodology",
        "skills": [
            "Agile / Scrum / Kanban",
            "Backlog Management",
            "Collab & Whiteboarding",
            "Confluence",
            "Jira",
            "Project Management",
            "Sprint Planning",
            "UAT / SIT / Regression",
        ],
    },

    "business_analysis": {
        "name": "Business Analyst / Scrum",
        "skills": [
            "Agile Ceremonies",
            "Backlog Grooming",
            "Business Case Development",
            "Process Mapping",
            "Requirements Gathering",
            "Stakeholder Communication",
            "UAT Coordination",
            "User Stories & Acceptance Criteria",
            "Wireframing / Prototyping",
        ],
    },

    "project_program_management": {
        "name": "Project / Program Management",
        "skills": [
            "Agile / Hybrid Delivery",
            "Benefits Realization",
            "Budget & Vendor Management",
            "Change Management",
            "Project Planning",
            "Resource Management",
            "Risk & Issue Management",
            "Status & Governance",
            "Tooling",
        ],
    },

    "qa_testing": {
        "name": "QA / Testing",
        "skills": [
            "API Testing",
            "Automation Testing",
            "Defect Tracking",
            "Performance Testing",
            "Regression Testing",
            "SIT / UAT Execution",
            "Test Case Design",
            "Test Data Management",
            "Test Strategy & Planning",
        ],
    },
    
    "marketing_automation": {
        "name": "Marketing Automation",
        "skills": [
            "Marketing Cloud", "Marketing Cloud Engagement", "SFMC",
            "AMPScript", "SSJS", "Server-Side JavaScript",
            "HTML/CSS for Email", "SQL on Data Views",
            "Data Extensions", "Contact Builder", "Journey Builder",
            "CloudPages", "Landing Pages", "Content Builder",
            "Personalization Strings", "MobileConnect", "MobilePush",
            "Marketing Cloud Connect", "Marketing Cloud APIs",
            "SFTP", "File Drop", "Campaign Management",
            "Pardot", "Account Engagement"
        ]
    }
}
