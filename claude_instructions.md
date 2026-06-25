Module 1: An Introduction to the Project
Urban Analytics AI Consultancy
1. Project Overview
In this experiential engagement, students will operate as a Boutique AI Consultancy hired by a simulated real estate development firm. The goal is to build and deploy a Spatial Decision Support System (SDSS) that predicts the market success of new retail ventures. Using the Huff Gravity Model and Azure OpenAI (GPT-4o), the team will transform raw urban data into a conversational, map-based tool that helps small business owners make data-driven location choices.
2. The Professional Scenario
Traditional site selection is often a "black box" accessible only to large corporations with massive GIS budgets. Your consultancy has been tasked with democratizing this data. You must deliver a live web application where an entrepreneur can drop a pin on a city map and receive an immediate AI-generated analysis of their potential market share, competitive risks, and customer demographics.
3. Team Structure & Roles
This project simulates a cross-functional Agile team. Students will be organized into two competing "Agencies," each consisting of:
•	Project Management Leads (PMs): Responsible for the Project Management Plan (PMP), defining the Work Breakdown Structure (WBS), managing the 12-week sprint schedule (via Jira/Trello), and leading client-facing presentations.
•	Informatics Leads: Responsible for the Technical Implementation, including database management in Azure SQL, connecting the AI "Brain" via Function Calling, and integrating the Mapbox visual interface.
4. Key Deliverables
A. The Strategic Layer (PM Focus)
•	Stakeholder Requirements Document: A comprehensive list of "User Stories" (e.g., "As a cafe owner, I want to see how many competitors are within 1 mile").
•	Sprint Reports: Bi-weekly updates tracking velocity, blockers, and milestone completion.
•	Final Client Pitch: A professional demonstration of the live tool, defending the ROI of the AI intervention.
B. The Technical Layer (Informatics Focus)
•	The Integrated Agent: A chatbot that triggers the provided Huff Engine to perform market simulations based on user input.
•	The Spatial Dashboard: An interactive map interface that visualizes the "Trade Area" of a proposed site.
•	The Data Bridge: A functional Azure SQL backend that stores demographic data and historical visit records.
5. Project Scope & Constraints
To ensure the focus remains on Integration and Delivery, the following assets will be provided to the teams:
•	The "Plumbing": A pre-configured GitHub repository with Azure CI/CD workflows and ODBC driver setup.
•	The "Engine": A validated Python module for the Huff Gravity Model calculations.
•	The "Fuel": Pre-cleaned Census Block Group data and business point-of-interest lists.
6. Measures of Success
•	Collaboration: How effectively did the Informatics students translate the PM's requirements into functional code?
•	Deployment: Does the system work live on an Azure URL without crashing during the final demo?
•	User Experience (UX): Can a non-technical user successfully analyze a business location in under 3 minutes using only the natural language interface?
________________________________________
Module 2: Assignment Purpose
This assignment is designed to help your team form a shared understanding of your project scope before development begins. In professional informatics practice, successful projects start with architectural clarity, not just writing code.
This worksheet helps your team:
•	Align on the urban problem you are solving in Worcester.
•	Define what is in scope vs. out of scope for the AI's logic.
•	Identify Informatics roles and technical responsibilities.
•	Surface geospatial or data unknowns early, before they become technical risks.
________________________________________
Submission Instructions
•	One submission per team.
•	Submit as PDF or Word Doc.
•	Clearly list all team members’ names.
•	Use headings exactly as shown below.
________________________________________
Urban AI Team Scoping Worksheet
Team Information
•	Team Name:
•	Team Members:
•	Date Submitted:
1. Working Problem Statement
(One sentence – draft version is fine) “We are building a system that helps [Target User Type] by [Primary Function of the AI Assistant].”
2. Primary Users (Ranked Priority)
Select and rank your primary users:
•	☐ Local Small Business Entrepreneurs
•	☐ Commercial Real Estate Investors
•	☐ City of Worcester Urban Planners
•	☐ Other: ______________________
Why did your team choose this priority order? (2–3 sentences)
3. In-Scope Features (This Project WILL Address)
List 3–5 concrete technical items your team commits to delivering (e.g., specific category calibrations, a map-based UI, or specific visit prediction metrics):
4. Out-of-Scope Items (This Project Will NOT Address)
List at least 3 items that are intentionally excluded (e.g., real-time traffic, property tax estimations, or data outside of Worcester):
Note: Out-of-scope does not mean “bad idea,” it means “not in this 12-week phase.”
5. Definition of Success
Complete this sentence:
“By the end of Week 12, this project will be considered successful if…”
(Be specific and outcome-focused regarding the system's "plumbing" and accuracy.)
6. Team Roles & Responsibilities
(Initial assignment! Ownership must be explicit!)
Role	Team Member(s)
Product / Requirements Lead	
UX / Conversation Design	
Inference Engine / Logic Lead (Python)	
Systems Integrator (Azure/API)	
Data / Model Calibration Lead	
7. Key Unknowns & Open Questions
List technical or data questions that must be clarified before development (e.g., "How do we handle NAICS codes for multi-service businesses?"):
8. Communication & Ways of Working
•	Primary team communication tool:
•	Meeting cadence (days/times): (e.g., Wednesdays at 7:30 PM EST)
•	How decisions/code will be documented: (e.g., GitHub Wiki, Google Docs, shared SQL scripts)
9. Immediate Next Actions (This Week)
Each team member lists one concrete technical action they will complete next:
•	Name: -> Task:
•	Name: -> Task:
•	Name: -> Task:
•	Name: -> Task:
Module 3: 
1. Objective
To develop a standalone Python script that implements the Huff Gravity Model for a hypothetical new business location in Worcester, MA. This script will serve as the "brain" for your future Agentic AI system.
2. The Scenario
A client wants to open a new business in Worcester. They provide you with a specific location (Latitude and Longitude), the size of their proposed store, and the business NAICS code (or 'top_category'). Your task is to calculate the Total Predicted Visits this new store will capture from the surrounding neighborhoods.
3. Technical Requirements
Your script must perform the following logical steps:
A. Data Initialization
Load the following files provided in class:
•	worcester_cbgs.csv (Demographics & Centroids)
•	worcester_pois.csv (Existing Competitors)
•	worcester_cbg_poi_visits.csv (Historical Demand)
•	calibrated_parameters_filtered.csv (Alpha & Beta coefficients)
B. User Input Layer
The script should prompt the user for:
1.	Latitude & Longitude: (e.g., 42.2625, -71.8023)
2.	Category: (Top Category or NAICS Code)
3.	Store Size: (Square Meters)
C. The Distance Calculation
Since the new store is not in the provided distance matrix, you must implement a Function to calculate the distance (in meters) between the new store's coordinates and every Census Block Group (CBG) centroid in worcester_cbgs.csv.
Use Straight-Line Euclidean Distances calculated via a Projected Coordinate System (Latitude/Longitude in WGS84).
D. The Huff Model Logic
For every CBG in the city, calculate the Market Share (Pij) for the new store:
1.	New Store Utility (Unew): Calculate using the alpha and beta specific to your category from the parameters file.
2.	Competitive Utilities ( Uexisting): Identify all existing businesses in the same category within Worcester and calculate their utilities using the pre-computed distances in the matrix.
3.	Probability: Pnew = Unew / (Unew +  Uexisting)
E. Demand Estimation
To convert probability into Visits:
1.	Calculate the Total Category Demand for each CBG by summing all historical visits in that category from that CBG.
2.	Predicted Visits = Pnew x Total Category Demand
4. Deliverables
1.	Python Script (predict_site.py): A clean, commented script.
2.	Validation Case: Run your script for a "New Liquor Stores" at 42.27, -71.80 with 2,500 sq meters and report the Total Predicted Visits.
________________________________________
Summary of Site Prediction Workflow
Your script should process the user input as follows:
•	Step A (Parameter Selection): Use the top_category or NAICS code provided by the user to look up the correct Alpha and Beta from calibrated_parameters_filtered.csv.
•	Step B (Distance Mapping): Use your projection-based distance function to build a list of distances from the new site to all ~150 CBGs.
•	Step C (Competitive Context): For each CBG, retrieve the utilities (Uexisting = Areaalpha/distancebeta) of all current competitors in that category using the distance_m values from worcester_cbg_poi_distance.csv.
•	Step D (Predicted Pij): Calculate the probability share for the new site:
Pnew = Unew / (Unew +  Uexisting)
•	Step E (Visit Estimation): Multiply Pnew by the total historical visits for that category/CBG found in worcester_cbg_poi_visits.csv.
Module 4:
Overview
Up to this point, our Urban AI Assistant has been a "script" that reads flat files. While this works for analysis, it is inefficient for a live application.
In this assignment, you will transition your Huff Model engine from reading CSVs and GeoJSON files to querying a relational database. You will focus on Database Design, Data Enrichment, and Query Optimization.
________________________________________
Technical Requirements
1. Database Design and Migration
You must create a local SQLite3 database (e.g., urban_ai.db) and design a schema that is more efficient than the raw CSVs.
•	The CBG Master Table: Combine the demographic data from worcester_cbgs.csv with the spatial coordinates (INTPTLAT10, INTPTLON10) from the GeoJSON.
•	Coordinate Pre-computation: Do not store raw degrees. Pre-calculate and store the projected X and Y coordinates (EPSG:26919) for every CBG.
•	Normalization vs. Denormalization: Decide which data should stay in separate tables (like category parameters) and which should be merged for faster retrieval.
2. The "Informatics Speed" Challenge (Pre-computation)
The most computationally expensive part of the Huff Model is calculating the "Utility Sum" of all existing competitors in a neighborhood.
•	Requirement: Create a table or column that stores the Pre-computed Competitor Utility for every category in every Census Block Group.
•	The Goal: When the AI Assistant runs, it should only need to calculate the utility for the one new site and then add it to this pre-existing sum.
3. Refactoring the Python Engine
Modify your huff_engine.py script:
•	Remove all File Readers: Delete lines that use pd.read_csv() or json.load().
•	Implement SQL Queries: Use the sqlite3 library to fetch only the data needed for a specific request.
•	Parameterized Queries: You must use placeholders (?) in your SQL strings to prevent SQL injection.
4. Performance Benchmarking
Measure the time it takes for your script to provide an answer using the "Old File Method" versus the "New Database Method."
•	Include a short (200-word) reflection on why the database approach is necessary for deployment on Azure.
________________________________________
Deliverables
1.	migration_script.py: The code used to move your CSV/GeoJSON data into SQLite.
2.	urban_ai.db: Your local database file.
3.	huff_engine_v2.py: Your refactored engine that queries the database.
4.	A Screenshot: Your terminal showing the "Success" of the model run and the performance time.

Module 5:
Overview
In this team assignment, you will refactor your verified Huff Model Engine to run on a production-ready SQLite3 architecture. You will move away from loading large CSVs into memory and instead design a database that provides the "answers" to the Huff math instantly through pre-computation and spatial enrichment.
Technical Requirements
Part 1: The Migration & Pre-computation Script
Develop a Python script (migration_v2.py) that performs a "One-Time" setup of your database. This script must:
1.	Enrich the CBG Master: Combine demographic data with projected centroids (X and Y coordinates in EPSG:26919).
2.	Solve the Competitor Bottleneck: For every category and every neighborhood, calculate the sum of competitor utilities: .
3.	Store the Results: Create a table named Competitor_Summary to hold these pre-calculated sums.
4.	Index for Performance: Apply SQL Indexes to the geoid and top_category columns to ensure sub-millisecond retrieval.
Part 2: The V3 Inference Engine
Refactor your huff_engine_v2.py into huff_engine_v3.py.
•	Zero Files: The engine must not use pd.read_csv() or json.load(). All data must come from the SQLite database.
•	Optimized Math: Instead of calculating competitor gravity in a loop, your engine should simply "fetch" the pre-computed sum from the database and add it to the new site's utility.
•	Security: Use parameterized SQL queries (? placeholders) for all user inputs (Latitude, Longitude, Category).
Part 3: Performance Benchmarking
Measure the "Total Execution Time" for a single inference (e.g., placing one new restaurant) using:
1.	Your V1 Engine (Module 3 CSV-based code).
2.	Your V2 Engine (Module 4 Database-V1).
3.	Your V3 Engine (Module 5 Database-V2 - optimized code and db structure)
Submission Deliverables (One per Team)
1.	migration_v2.py: The script that builds and optimizes your database.
2.	huff_engine_v3.py: Your refactored inference engine.
3.	urban_ai_v2.db: Your optimized SQLite database file.
4.	Performance Report (PDF/Markdown): A brief summary including:
o	The execution time comparison (V1 vs V2 vs V3).
o	A brief explanation of why your chosen schema is more efficient for a live chatbot.
The "Expert" Success Criteria
A "Grade A" project will show a significant reduction in execution time. By moving the "Heavy Lifting" (coordinate projection and competitor summing) into the migration phase, your live engine should be able to process 200+ neighborhoods in the blink of an eye.
Remember: You are no longer just calculating distances, you are building the foundation for a cloud-native Urban AI Assistant!
Module 6:
Overview
In this assignment, you will integrate your optimized Huff model (V3) into the baseline ALSDS web application and deploy it to Azure.
This is your first step in transforming your model from a local script into a working cloud-based application.
________________________________________
Assignment Objective
The goal of this assignment is to:
•	Integrate your V3 Huff model into the provided application
•	Use your local database inside the deployed app
•	Deploy and run the application on Azure
•	Verify the full system works end-to-end
You are not building a new system. You are replacing the baseline model with your own implementation.
________________________________________
Instructions
1. Replace the Baseline Huff Model
•	Replace huff_engine.py with your V3 implementation
•	Ensure your function matches the required signature:
run_huff_model(candidate_lat, candidate_lon, business_category, floor_area, db_connection=None)
•	Return a structured result including:
predicted_visits
market_share
competitors
runtime_ms
notes
________________________________________
2. Use Your Local Database
Instead of CSV files, your model must read from your database.
•	Include your database file in the repository:
/Data/your_team.db
•	Update your code to connect using a relative path:
sqlite3.connect("Data/your_team.db")
Do NOT use absolute paths (e.g., your local machine path).
________________________________________
3. Keep the Application Structure Intact
You must NOT modify:
•	startup.sh
•	requirements.txt
•	API routes in app.py
•	Environment variable names
Your goal is to integrate your model into the existing system, not redesign it.
________________________________________
4. Deploy to Azure
•	Push your updated code to GitHub
•	Wait for GitHub Actions to complete deployment
•	Open your Azure Web App URL
________________________________________
5. Verify the System Works
You must confirm:
•	/health returns OK
•	Homepage loads correctly
•	Map is visible and clickable
•	Model runs successfully from the UI
•	Results are displayed
•	Chatbot provides explanation
________________________________________
Important Rules
•	Your database file must be under 100MB
•	Use relative file paths only
•	Azure is case-sensitive (e.g., Data/ is not the same as data/)
•	Do not change API request/response structure
•	Do not remove required files
Module 7:
In this assignment, your team will transition your ALSDS application from a local SQLite database workflow to an Azure SQL cloud database workflow.
This means your application should no longer rely on Data/your_team.db as the main production data source. Instead, your deployed web app should query your assigned Azure SQL database at runtime.
________________________________________
Assignment Objective
The goal of this assignment is to:
•	migrate your local SQLite tables into your assigned Azure SQL database
•	verify the migrated tables using a /db_structure endpoint
•	update your Huff engine to query Azure SQL instead of SQLite
•	deploy the updated application through GitHub and Azure
•	confirm the full web app works end-to-end
________________________________________
Your Assigned Azure SQL Database
Each team already has an assigned Azure SQL database on the shared class SQL server:
cpl-sql-prod-shared
Your database follows this pattern:
alsds_team1_db
alsds_team2_db
alsds_team3_db
alsds_team4_db
alsds_team5_db
Only use your assigned database.
________________________________________
What You Need to Do
1. Create a Migration Script
Create a Python script in your repository, for example:
migrate_to_azure_sql.py
This script should:
•	read your existing SQLite database
•	connect to Azure SQL using SQL_CONNECTION_STRING
•	create the required Azure SQL tables
•	insert your data into Azure SQL
________________________________________
2. Migrate Your Tables
Your migration should include all tables required by your Huff engine.
Examples may include:
•	POI table
•	distance matrix table
•	visit count table
•	model parameter table
•	precomputed or optimized lookup tables
________________________________________
3. Add a /db_structure Endpoint
Add an endpoint to your Flask app that allows you to verify the Azure SQL database structure from the browser.
The endpoint should be:
/db_structure
It should return:
•	table names
•	row counts
This endpoint will help verify that your migration worked.
________________________________________
4. Verify Your Azure SQL Tables
After deployment, open:
https://your-app-url.azurewebsites.net/db_structure
You should see output showing your migrated tables and row counts.
Example:
[
  {
    "TABLE_NAME": "pois",
    "row_count": 12543
  },
  {
    "TABLE_NAME": "distance_matrix",
    "row_count": 842211
  }
]
________________________________________
5. Update Your Huff Engine
Update huff_engine.py so that it queries Azure SQL instead of opening your local SQLite database file.
Replace logic like:
sqlite3.connect("Data/your_team.db")
with Azure SQL logic such as:
from db import get_connection

conn = get_connection()
Your engine must continue to preserve the required function signature:
run_huff_model(
    candidate_lat,
    candidate_lon,
    business_category,
    floor_area,
    db_connection=None
)
________________________________________
6. Deploy Through GitHub
After updating your code:
•	push your changes to GitHub
•	wait for GitHub Actions deployment to finish
•	test the deployed Azure Web App
Use the recommended workflow:
dev branch → testing → merge into main → deployment
________________________________________
7. Test the Full System
Your deployed app must successfully support:
•	/health
•	/dbcheck
•	/db_structure
•	the main dashboard page
•	Huff model execution from the UI
•	GPT explanation of model results
________________________________________
Important Rules
•	Do NOT try to create a new Azure Web App, SQL Server, or Database
•	Do NOT upload database credentials to GitHub (if you're using your personal database services)
•	Do NOT continue using SQLite as your deployed production data source
•	Do NOT break the required run_huff_model() function signature
•	Do NOT modify the API structure unless needed and clearly documented

Module 8:
Assignment Purpose
In this assignment, your team will improve the user interface of your AI-Assisted Location Decision Support System and explain the design reasoning behind your changes.
The goal is not only to make the dashboard look better. The goal is to make the dashboard easier to understand, easier to use, and more useful for location decision-making.
________________________________________
Deliverables
Submit a short team memo that includes the following sections.
________________________________________
1. Current UI Diagnosis
Briefly describe the current state of your dashboard.
Discuss at least three UI issues related to:
•	Layout
•	Input clarity
•	Model output interpretation
•	Map design
•	Chatbot interaction
•	Cognitive load
•	User trust
•	Scenario comparison
________________________________________
2. Design Principles Applied
Choose at least three principles from this module and explain how they apply to your dashboard.
Possible principles include:
•	Users scan before they read.
•	Attention is limited.
•	Recognition is easier than recall.
•	Interfaces should support correct mental models.
•	Visual design should support comparison.
•	Good UI reduces cognitive load.
•	Trust requires clarity and explanation.
________________________________________
3. UI Improvements Made or Planned
Describe at least three concrete improvements your team made or plans to make.
For each improvement, include:
•	The original issue.
•	The design change.
•	Why the change improves decision support.
•	Which principle from the module supports the change.
________________________________________
4. Before-and-After Evidence
Include screenshots or descriptions showing the dashboard before and after your changes.
If implementation is not fully complete, include a mockup, sketch, or detailed description of the planned revision.
________________________________________
5. Reflection
Briefly answer:
- How does your improved interface help a non-technical user make a better location decision?

9.0 Introduction
Module 9 is the final educational module before the final deliverables module. At this point, your team should already have a working AI-Assisted Location Decision Support System with a dashboard, map, model, database connection, and chatbot interface.
Now the focus shifts from basic functionality to system quality.
A good decision-support system should not only work once under perfect conditions. It should be flexible, reliable, understandable, and useful when a real user interacts with it in different ways.
In this module, your team will improve your system so that it behaves more like a real DSS product.
________________________________________
Main Question for This Module
How can we make the dashboard and chatbot more useful, flexible, and reliable for location decision-making?
________________________________________
Learning Objectives
By the end of this module, your team should be able to:
1.	Improve the DSS so that the map and model read data from Azure SQL instead of static GeoJSON files.
2.	Design chatbot behavior that supports multiple model runs and follow-up questions.
3.	Allow users to compare alternative candidate locations.
4.	Improve the chatbot’s ability to interpret user inputs, including business category names and NAICS codes.
5.	Present model results using clear summaries, tables, maps, and visual figures.
6.	Control chatbot tone so that it communicates clearly without unnecessary academic language.
7.	Restrict chatbot responses to the DSS topic and avoid unrelated conversations.
8.	Prepare the system for final demonstration and evaluation.

9.1 Resources and Next Steps
This page includes the class materials and external resources that may help your team complete the Module 9 system improvements.
Module 9 focuses on improving your AI-Assisted Location Decision Support System so that it becomes more flexible, reliable, and useful for real decision making. These resources are intended to support your work on Azure SQL integration, map updates, chatbot behavior, multiple model runs, scenario comparison, NAICS lookup, and result visualization.
________________________________________
Class Slides
Module 9 Class Slides
Please review the Module 9 class slides before working on your system improvements.
Slides:
Download Module 9 SlidesDownload Download Module 9 Slides
The slides summarize the main improvement areas for Module 9, including:
•	Reading map and POI data from Azure SQL.
•	Creating backend API endpoints for map and model data.
•	Allowing the chatbot to rerun the model.
•	Supporting follow-up user requests.
•	Comparing alternative candidate locations.
•	Mapping business category names to NAICS codes.
•	Adding charts and visual summaries to the results pane.
•	Improving chatbot tone and topic control.
________________________________________
Required Project Resources
1. Module 9 Canvas Page
Review the main Module 9 page carefully. It explains the expected improvement areas and the minimum baseline your team should address.
Focus especially on:
•	Required improvement areas.
•	Testing scenarios.
•	Module 9 checklist.
•	Expected evidence for your team update.
________________________________________
2. Your Team Repository
You should work directly in your team GitHub repository.
Depending on your current implementation, the files most likely involved are:
•	app.py
•	chat.js
•	map.js
•	index.html
•	huff_engine.py
•	database helper or connection files
•	any prompt/configuration files used by your chatbot
Your exact file names may differ depending on your team’s implementation.
________________________________________
External Technical Resources
1. Azure SQL and Python
Use this when improving the database-backed parts of your system, especially if your map or model needs to read from Azure SQL.
Microsoft Learn: Connect to and query Azure SQL Database using PythonLinks to an external site.
This resource explains how a Python application can connect to Azure SQL Database and perform queries. It is useful for teams working on database-backed model or map endpoints.
Recommended use in this project:
•	Query POIs from Azure SQL.
•	Query model parameters from Azure SQL.
•	Confirm database connectivity from Flask.
•	Replace static file dependencies with database-backed API responses.
________________________________________
2. Flask API Endpoints
Use this when creating backend routes such as /api/pois, /api/map-data, /api/run-model, or /api/compare.
Flask Documentation: QuickstartLinks to an external site.
Links to an external site.The Flask quickstart explains basic routing and also notes that returning a Python dict or list from a view can produce a JSON response, which is useful for API endpoints.
Flask Documentation: API ReferenceLinks to an external site. + Flask JavaScript, fetch, and JSON PatternsLinks to an external site.
Links to an external site.The Flask API reference provides more detailed documentation on Flask objects, routes, request handling, and response behavior.
Recommended use in this project:
•	Create API endpoints that return JSON.
•	Send model results from backend to frontend.
•	Build endpoints for map data, model runs, and comparison outputs.
•	Keep the backend as the source of truth for model results.
________________________________________
3. Leaflet Map Resources
Use these when improving your map behavior, marker design, popups, and GeoJSON or database-backed map updates.
Leaflet API ReferenceLinks to an external site.
Leaflet is an open-source JavaScript library for mobile-friendly interactive maps. The API reference is useful when working with markers, layers, popups, map controls, and map updates.
Leaflet: Using GeoJSON with LeafletLinks to an external site.
This guide explains how GeoJSON objects can be displayed and interacted with in Leaflet. Even if your final data comes from Azure SQL, this is useful because your Flask API may still return map-ready JSON or GeoJSON-style structures.
Recommended use in this project:
•	Display candidate and competitor markers.
•	Add popups with POI names, NAICS codes, and distances.
•	Update the map after a new model run.
•	Distinguish candidate locations from competitors.
•	Add or revise map layers dynamically.
________________________________________
4. Chart.js Resources
Use this when adding figures to the results pane.
Chart.js Getting StartedLinks to an external site.
This resource explains how to create charts in a web page using Chart.js. It is useful if your team wants to add bar charts, comparison charts, or simple visual summaries.
Chart.js Bar Chart DocumentationLinks to an external site.
This page explains how to create bar charts, which are especially useful for comparing market share, predicted visits, competitor counts, or scenario results.
Recommended use in this project:
•	Market share comparison chart.
•	Predicted visits comparison chart.
•	Competitor count chart.
•	Distance-band competitor chart.
•	Scenario comparison chart.
________________________________________
Suggested Resources by Module 9 Task Types
 
Task: Map Reads from Azure SQL
Useful resources:
•	Microsoft Learn Azure SQL Python quickstart.
•	Flask Quickstart.
•	Leaflet API Reference.
Files likely involved:
•	app.py
•	map.js
•	database connection helper
What to focus on:
•	Create a Flask endpoint that queries Azure SQL.
•	Return JSON or GeoJSON-style data.
•	Fetch that data from map.js.
•	Update Leaflet markers based on the returned data.
________________________________________
Task: Chatbot Can Rerun the Model
Useful resources:
•	Flask routing/API documentation.
•	Your existing huff_engine.py.
•	Your existing chat.js.
Files likely involved:
•	app.py
•	chat.js
•	huff_engine.py
What to focus on:
•	Extract inputs from the user message or form.
•	Call the model function from the backend.
•	Return actual model results.
•	Update the results pane and chatbot response.
•	Do not allow the chatbot to invent model outputs.
________________________________________
Task: Follow-Up Runs and Scenario History
Useful resources:
•	JavaScript documentation or examples for managing frontend state.
•	Existing project files.
Files likely involved:
•	chat.js
•	app.py
•	possibly browser localStorage or a backend session-style structure
What to focus on:
•	Store the latest model inputs.
•	Store the latest model result.
•	Store multiple scenario results if comparing locations.
•	Reuse previous inputs when the user says “same business” or “same area.”
________________________________________
Task: Compare Alternative Locations
Useful resources:
•	Chart.js documentation.
•	Existing model output structure.
•	Your results pane code.
Files likely involved:
•	chat.js
•	index.html
•	app.py
What to focus on:
•	Save two or more model runs.
•	Compare predicted market share, visits, competitors, and distance metrics.
•	Show a table or chart.
•	Have the chatbot summarize the comparison clearly.
________________________________________
Task: Business Category to NAICS Lookup
Useful resources:
•	Your own project NAICS list, if available.
•	A small dictionary in Python or JavaScript.
•	Optional SQL lookup table.
Files likely involved:
•	app.py
•	chat.js
•	possibly a naics_lookup table
What to focus on:
•	Accept user-friendly categories such as “hardware store” or “coffee shop.”
•	Map them to a likely NAICS code.
•	Ask a clarification question when the category is too broad.
•	Validate that the selected NAICS code exists in your data.
________________________________________
Task: Add Figures to Results Pane
Useful resources:
•	Chart.js Getting Started.
•	Chart.js Bar Chart documentation.
Files likely involved:
•	index.html
•	chat.js
•	possibly app.py
What to focus on:
•	Add a chart container to the results pane.
•	Use real model output values.
•	Avoid hardcoded fake values.
•	Keep charts simple and decision-focused.
________________________________________
Task: Improve Chatbot Tone and Topic Control
Useful resources:
•	Your current chatbot system prompt.
•	Your app.py or prompt/config file.
Files likely involved:
•	app.py
•	prompt/config file, if your team uses one
What to focus on:
•	Use clear, practical language.
•	Avoid academic explanations unless requested.
•	Stay focused on location decision support.
•	Politely refuse unrelated questions.
•	Clearly state limitations.
•	Never invent model results.
________________________________________
Final Reminder
The resources above are meant to support your team’s implementation decisions. There is no single correct solution for Module 9. However, your final system should show meaningful improvements in system behavior, chatbot flexibility, database-backed data flow, comparison, result visualization, and decision-focused communication

9.2 Move from Static Files to Azure SQL
Earlier versions of the project may have used GeoJSON files stored in GitHub to display map data. This is useful for a prototype, but it is not ideal for a real deployed DSS.
A stronger version of the system should read map and model data directly from Azure SQL.
This makes the system more scalable, consistent, and easier to update.
________________________________________
What Your System Should Do
Your map and model should read from the database tables, such as:
•	pois
•	parameters
•	geojson_map
The goal is that the dashboard no longer depends on manually stored GeoJSON files in the GitHub repository.
Instead, the backend should query Azure SQL and return the data needed by the frontend.
________________________________________
Example System Flow
A stronger system flow looks like this:
1.	User enters a business type, NAICS code, location, and floor area.
2.	Backend receives the request.
3.	Backend queries Azure SQL for relevant POIs, parameters, and map data.
4.	Huff model runs using database-backed data.
5.	Backend returns structured model results.
6.	Frontend updates the map, result pane, and chatbot context.
7.	User can ask follow-up questions or run another scenario.
________________________________________
Questions Your Team Should Check
•	Does the map still depend on a static GeoJSON file from GitHub?
•	Can the backend retrieve POIs from Azure SQL?
•	Can the frontend request map data through an API endpoint?
•	Are the database tables properly migrated and accessible?
•	Does /dbcheck confirm the database connection?
•	Can the model run using data from Azure SQL?
9.3 Make the Chatbot More Flexible
A DSS chatbot should not only answer one initial question. A real user may want to revise assumptions, try a different location, change the business type, increase the floor area, or compare two possible sites.
The chatbot should support an interactive decision process.
________________________________________
Weak Chatbot Behavior
A weak chatbot might say:
The model cannot be rerun with new inputs.
Or:
Based on the previous result, this location seems good.
This is not enough for a DSS chatbot.
________________________________________
Stronger Chatbot Behavior
A stronger chatbot should be able to respond to requests like:
Run the model for NAICS 4441, area 1000 square meters, at 42.229212, -71.805525.
Then later:
Now try the same business type but at 42.2671, -71.8003.
Then:
Compare the two locations.
The chatbot should understand that the user is continuing the same decision task.
________________________________________
Recommended Chatbot Capabilities
Your chatbot should support:
1.	First model run
The user gives required inputs, and the chatbot runs the model.
2.	Follow-up model runs
The user changes one or more inputs, and the chatbot reruns the model.
3.	Partial input reuse
If the user says “same NAICS, but new location,” the chatbot should reuse the previous NAICS code and area.
4.	Scenario comparison
The chatbot should compare two or more candidate locations.
5.	Plain-language explanation
The chatbot should explain results clearly for a non-technical user.
6.	Topic control
The chatbot should avoid answering unrelated questions.
9.4 Support Multiple Runs and Follow-Up Scenarios
Decision-making is iterative. Users rarely make a decision from one model result.
They may ask:
•	What if the store were larger?
•	What if I moved closer to downtown?
•	What if I changed the business category?
•	Which of these two locations is better?
•	Why did the second location perform better?
•	What are the main competitors near each site?
Your system should support this type of interaction.
________________________________________
Example Follow-Up Interaction
User
Run the model for a hardware store with 1000 square meters at 42.229212, -71.805525.
Chatbot
I found that “hardware store” is related to NAICS 4441. I ran the model using NAICS 4441, 1000 square meters, and the candidate location 42.229212, -71.805525. The predicted market share is X%, with Y nearby competitors.
User
Now try 42.2671, -71.8003 with the same business and area.
Chatbot
I reran the model using the same NAICS code and floor area, but with the new candidate location. The predicted market share is X2%. Compared with the previous location, this site has fewer nearby competitors but is farther from several demand points.
User
Which one is better?
Chatbot
Based on the model results, Location 2 appears stronger because it has a higher predicted market share and lower competitive pressure. However, this recommendation does not include rent, parking, zoning, or demographic suitability.
________________________________________
Important Design Requirement
The chatbot should know whether it is using:
•	A new model run
•	A previous model result
•	A comparison between stored scenarios
•	Missing information that still needs to be collected
The user should not have to guess.

9.5 Compare Alternative Locations
Location decision-making is often comparative. Users usually do not ask only whether one location is good. They want to know which location is better among alternatives.
Your DSS should support comparison.
________________________________________
Recommended Comparison Features
Your system can compare candidate locations using:
•	Predicted market share
•	Predicted visits
•	Number of nearby competitors
•	Distance to nearest competitors
•	Total attraction score
•	Relative competitive intensity
•	Map position
•	Chatbot explanation
________________________________________
Example Comparison Output
A useful comparison might look like this:
Metric	Location A	Location B	Better Option
Predicted Market Share	10.8%	14.2%	Location B
Nearby Competitors	9	5	Location B
Nearest Competitor Distance	0.4 miles	0.9 miles	Location B
Predicted Visits	1,250	1,610	Location B
Then the chatbot should summarize:
Location B appears stronger in this model run because it has a higher predicted market share, higher predicted visits, and fewer nearby competitors. However, the final decision should also consider rent, parking, visibility, zoning, and customer demographics.
9.6 Accept Business Category Names, Not Only NAICS Codes
Most real users do not know NAICS codes. A business owner may say:
•	Hardware store
•	Coffee shop
•	Grocery store
•	Gym
•	Daycare
•	Restaurant
•	Clothing store
•	Pharmacy
The DSS should help translate user-friendly business names into a relevant NAICS code or candidate NAICS category.
________________________________________
Recommended Behavior
If the user provides a category name, the chatbot should try to identify the closest NAICS category.
Example:
User
I want to open a hardware store.
Chatbot
A hardware store is commonly associated with NAICS 4441, Building Material and Supplies Dealers. I will use NAICS 4441 unless you want a more specific category.
________________________________________
If the Category Is Ambiguous
Some user inputs may be ambiguous.
Example:
I want to open a food business.
This could mean:
•	Grocery store
•	Restaurant
•	Coffee shop
•	Bakery
•	Convenience store
•	Specialty food store
In this case, the chatbot should ask a focused clarification question.
Better response:
“Food business” could refer to several categories. Do you mean a restaurant, grocery store, coffee shop, bakery, or convenience store?
Avoid long, academic explanations.

9.7 Add Figures to the Results Pane
A dashboard should not rely only on chatbot text. Visual results help users compare and interpret information quickly.
Your results pane should include clear, useful figures when possible.
________________________________________
Recommended Figures
Your team may add one or more of the following:
1. Competitor Distance Chart
Shows the nearest competitors and their distance from the candidate location.
Useful for answering:
How close are the strongest nearby competitors?
________________________________________
2. Market Share Comparison Bar Chart
Compares predicted market share across candidate locations.
Useful for answering:
Which candidate site performs better?
________________________________________
3. Predicted Visits Chart
Shows estimated visits for one or more candidate locations.
Useful for answering:
Which site is expected to attract more visits?
________________________________________
4. Scenario Comparison Chart
Shows multiple model runs side by side.
Useful for answering:
How does changing location or floor area change the result?
________________________________________
5. Competitor Count Summary
Shows how many competitors are within selected distance ranges.
Example:
Distance Band	Number of Competitors
Within 0.5 miles	3
0.5–1 mile	5
1–2 miles	8
________________________________________
Design Reminder
Figures should support decision-making. Do not add charts only because they look impressive.
Each figure should answer a user question.

9.8 Use Clear, Non-Academic Chatbot Language
The DSS chatbot is not writing a research paper. It is helping a user make a location decision.
The language should be:
•	Clear
•	Direct
•	Practical
•	Friendly
•	Non-technical when possible
•	Focused on the decision
________________________________________
Avoid This Style
The spatial interaction dynamics represented by the Huff Gravity Model suggest that consumer utility is mediated by distance-decay parameters and competitive attraction coefficients.
This is too academic for most DSS users.
________________________________________
Prefer This Style
This location performs well because it is relatively close to demand points and has fewer nearby competitors. The model predicts a stronger market share than the alternative location.
________________________________________
Recommended Chatbot Tone
The chatbot should sound like a helpful decision-support assistant.
It should:
•	Explain what it did.
•	State the result.
•	Interpret the result.
•	Mention important limitations.
•	Suggest the next useful step.
Example:
I ran the model using your new location and the same business category. This second location has a higher predicted market share than the first one. The main reason is that it has fewer nearby competitors within the selected area. You may still want to compare rent, visibility, parking, and zoning before making a final decision.

9.9 Keep the Chatbot Focused on the DSS Topic
Your chatbot should not behave like a general-purpose chatbot. It should behave like a specialized location decision-support assistant.
It should avoid unrelated conversations.
________________________________________
In-Scope Questions
The chatbot can answer questions about:
•	Running the location model
•	Explaining model results
•	Comparing locations
•	Interpreting maps
•	Explaining NAICS categories
•	Discussing competitors
•	Explaining assumptions and limitations
•	Suggesting what information the user should consider next
•	Helping the user understand the DSS dashboard
________________________________________
Out-of-Scope Questions
The chatbot should avoid answering questions unrelated to the DSS, such as:
•	General homework questions
•	Personal advice
•	Politics
•	Entertainment
•	Medical advice
•	Legal advice
•	Random coding questions unrelated to the project
•	Questions unrelated to location decision-making
________________________________________
Recommended Refusal Style
The chatbot should not be rude or overly strict.
Good response:
I’m designed to help with location decision support, including business category selection, candidate locations, model results, competitors, and dashboard interpretation. I can help you run or compare location scenarios, but I can’t help with unrelated topics.

9.10 Suggested System Behavior Rules
Your team should update the chatbot instructions so the assistant follows clear behavior rules.
A useful system instruction might include:
You are an AI assistant for a location decision-support dashboard.

Your role is to help users evaluate candidate business locations using the DSS model, map, database, and model outputs.

You should:
- Help users provide or revise required inputs: business category or NAICS code, candidate latitude, candidate longitude, and floor area.
- Run or request model runs when the user provides enough information.
- Reuse previous inputs when the user clearly asks for a follow-up scenario.
- Compare alternative locations when multiple model results are available.
- Explain results in plain, practical language.
- Avoid academic jargon unless the user asks for technical details.
- State important limitations clearly.
- Stay focused on location decision-support questions.

You should not:
- Answer unrelated questions.
- Pretend to run the model if no model run was performed.
- Invent results that were not returned by the backend.
- Use old results as if they are new results.
- Give legal, financial, medical, or unrelated advice.
9.11 Team Task: System Improvement Plan
Your team should identify and work on improvements in the following areas.
Required Improvement Areas
Each team should address at least four of the following:
1.	Map reads from Azure SQL instead of static GeoJSON.
2.	Chatbot can perform multiple model runs.
3.	Chatbot can handle follow-up requests using previous inputs.
4.	Chatbot can compare two or more candidate locations.
5.	User can enter a business category name, and the system maps it to a NAICS code.
6.	Results pane includes at least one useful chart or visual summary.
7.	Chatbot uses plain, practical language.
8.	Chatbot avoids unrelated questions.
9.	Dashboard clearly shows whether results are current.
10.	System communicates limitations of the model.
Module 9 is about turning a working prototype into a more realistic decision-support system.
A strong final system should be able to:
•	Read data from Azure SQL.
•	Run the model more than once.
•	Handle follow-up user requests.
•	Compare alternative locations.
•	Accept plain business category names.
•	Show useful figures and summaries.
•	Explain results clearly.
•	Stay focused on the location decision-support task.
Your goal is not only to make the system technically functional. Your goal is to make it useful, reliable, and understandable for a real decision-maker.

9.12 Testing Checklist
Before moving to the final deliverables module, test your system using the checklist below.
Database and Map
•	/dbcheck works.
•	Data is available in Azure SQL.
•	Map data can be loaded from the backend.
•	The system does not depend only on static GeoJSON files.
•	Candidate and competitor locations are shown clearly.
Model Runs
•	User can run the model with a NAICS code.
•	User can run the model with a business category name.
•	User can change location and rerun the model.
•	User can change floor area and rerun the model.
•	System confirms when new results are generated.
Chatbot Behavior
•	Chatbot collects missing inputs when needed.
•	Chatbot reuses previous inputs appropriately.
•	Chatbot can compare multiple scenarios.
•	Chatbot explains results clearly.
•	Chatbot avoids academic jargon.
•	Chatbot refuses unrelated questions politely.
•	Chatbot does not invent model outputs.
Results Pane
•	Main result is easy to find.
•	Results are labeled clearly.
•	At least one useful chart or visual summary is included.
•	Tables or figures support decision-making.
•	Limitations are communicated clearly.
Final Readiness
•	System works after deployment.
•	Team can demonstrate a first model run.
•	Team can demonstrate a follow-up run.
•	Team can demonstrate comparison between locations.
•	Team can explain what changed since earlier modules.

9.13 Team Activity
Each team should test its system with the following scenario.
Scenario 1: First Run
Ask the chatbot:
I want to open a hardware store with 1000 square meters at 42.229212, -71.805525. Can you run the model?
Check:
•	Did it identify the business category or NAICS code?
•	Did it run the model?
•	Did it update the results pane?
•	Did it update the map?
•	Did it explain the result clearly?
________________________________________
Scenario 2: Follow-Up Run
Ask:
Now try the same business and floor area at 42.2671, -71.8003.
Check:
•	Did it reuse the previous business type and floor area?
•	Did it use the new location?
•	Did it clearly say this is a new model run?
________________________________________
Scenario 3: Comparison
Ask:
Which location is better and why?
Check:
•	Did it compare the two model results?
•	Did it use clear metrics?
•	Did it avoid unsupported claims?
•	Did it mention important limitations?
________________________________________
Scenario 4: Out-of-Scope Question
Ask:
Can you write my history essay?
Check:
•	Did the chatbot politely refuse?
•	Did it redirect the user back to location decision support?
10.0 Introduction
Module 10 is the final project module. In this module, your team will prepare and submit the final deliverables for the AI-Assisted Location Decision Support System project.
Throughout the course, you have worked on building a decision-support system that combines:
•	A location decision problem
•	POI and business data
•	A Huff Gravity Model
•	Azure SQL database integration
•	A deployed web application
•	An interactive map
•	A chatbot interface
•	UI/dashboard design improvements
•	System and chatbot performance improvements
The final deliverables are designed to help you demonstrate not only that your system works, but also that you understand how the full system works.
________________________________________
Final Deliverables
There are two main final deliverables:
1.	Final Team Presentation
2.	Individual Final Report
The team presentation focuses on what your team built together.
The individual report focuses on what each student understands individually about the full system, including parts they may not have personally coded.
________________________________________
Why There Is an Individual Report
This project was completed in teams, and different team members may have worked on different parts of the system. For example, one person may have focused on the database, another on the map, another on the chatbot, another on UI design, and another on deployment.
However, by the end of the project, every student should understand the overall system.
The individual report is included because each student should be able to explain:
•	What the system does
•	How the system works
•	How data moves through the system
•	How the model is used
•	How the chatbot interacts with the model and dashboard
•	What improvements were made
•	What limitations remain
•	What they personally contributed
•	What they learned from the project
The goal is not to punish students for dividing work in a team. The goal is to make sure everyone understands the full decision-support system, not only one small part of it.
________________________________________
Overall Final Project Expectations
Your final project should show that your team moved beyond the instructor baseline.
At minimum, your final system should demonstrate:
•	A working deployed dashboard
•	Clear team branding and project description
•	Updated GitHub README
•	Azure SQL database integration
•	Map and/or data flow connected to the backend/database
•	A working Huff model
•	Chatbot interaction connected to the DSS task
•	Ability to run the model with user inputs
•	Ability to handle follow-up or revised scenarios
•	Clear presentation of model results
•	UI improvements based on Module 8
•	System/chatbot improvements based on Module 9
•	Honest explanation of limitations
Your system does not need to be perfect. However, your team should clearly explain what works, what does not work yet, and what design or technical choices you made.
________________________________________
Important Reminder
The final project is not only about code, but it is about building and explaining a decision-support system.
A strong final project should show:
•	Technical functionality
•	Clear user experience
•	Responsible chatbot behavior
•	Meaningful decision support
•	Understanding of the full system
•	Honest communication about assumptions and limitations

10.1 Final Team Presentation Instructions
The final team presentation is your opportunity to demonstrate the AI-Assisted Location Decision Support System your team built.
Your presentation should explain:
•	What problem your system addresses
•	What your system does
•	How the system works
•	What improvements your team made
•	How the user interacts with the system
•	How the model supports decision-making
•	What limitations remain
The goal is not only to show a working app. The goal is to explain the system as a decision-support tool.
________________________________________
Suggested Presentation Structure
Your team presentation should include the following sections.
________________________________________
1. Team and Project Introduction
Start by introducing:
•	Team name
•	Team members
•	Project title
•	Short description of your DSS
Briefly explain the purpose of your system.
For example:
Our system helps users evaluate potential business locations by combining POI data, a Huff Gravity Model, map-based visualization, and an AI chatbot that explains and compares location scenarios.
________________________________________
2. Problem and User Scenario
Explain the decision problem your system supports.
You may describe a user scenario such as:
A business owner wants to evaluate whether a proposed location is suitable for opening a new store.
Explain:
•	Who the user is
•	What decision they need to make
•	What inputs they provide
•	What outputs your system gives back
•	How your system helps them make a better decision
________________________________________
3. System Overview
Explain the main components of your system.
Your overview may include:
•	Frontend dashboard
•	Map interface
•	Chatbot interface
•	Flask backend
•	Huff model
•	Azure SQL database
•	POI data
•	Parameters table
•	Result pane or visual summaries
You should explain how these pieces work together.
A good explanation should answer:
When the user enters inputs and runs the model, what happens behind the scenes?
________________________________________
4. Data and Database Integration
Explain how your system uses data.
Discuss:
•	What data tables are used
•	Whether the system reads from Azure SQL
•	How POIs are used
•	How the parameters table is used
•	How NAICS codes are handled
•	Whether fallback alpha and beta values are used when needed
You should also explain how your team handled the three NAICS cases:
1.	NAICS code exists in the parameters table.
2.	NAICS code exists in POIs but not in the parameters table.
3.	NAICS code does not exist in the available data.
________________________________________
5. Model Functionality
Explain how the Huff Gravity Model is used in your DSS.
You do not need to derive every equation in detail, but you should explain the model logic clearly.
Discuss:
•	What inputs the model uses
•	What outputs the model produces
•	How candidate locations are evaluated
•	How competitors are included
•	How alpha and beta parameters are used
•	What the model result means for the user
Use plain language. The audience should understand the decision-support logic, not only the code.
________________________________________
6. Dashboard and UI Improvements
Explain the UI improvements your team made based on Module 8.
Discuss changes such as:
•	Landing page description
•	Team branding
•	Layout improvements
•	Clearer input labels
•	Better map design
•	Better result presentation
•	Reduced clutter
•	More useful explanations
•	Improved workflow for the user
•	About Us page, if added
Explain why these improvements matter for a real user.
________________________________________
7. System and Chatbot Improvements
Explain the system and chatbot improvements your team made based on Module 9.
Discuss improvements such as:
•	Map or POI data coming from Azure SQL
•	Multiple model runs
•	Follow-up scenario handling
•	Comparison of alternative locations
•	Business category name to NAICS code lookup
•	Charts or figures in the results pane
•	Plain-language chatbot responses
•	Chatbot staying focused on DSS-related questions
•	Chatbot not inventing model results
You should explain both what you implemented and how you tested it.
________________________________________
8. Live Demo or Evidence
Your team should show the system working.
This may include:
•	Live deployed app demo
•	Local demo
•	Screenshots
•	Short screen recording
•	GitHub evidence
•	Azure SQL evidence
•	Chatbot interaction examples
•	Map/model output
•	Comparison output
•	Chart or result pane output
If the live demo has technical issues, you should still be ready with screenshots or a short backup video.
Your demo should ideally show:
1.	A first model run
2.	A follow-up model run
3.	A comparison between two locations
4.	Chatbot explanation of results
5.	Map/result pane update
6.	Example of topic control or limitation handling
________________________________________
9. Limitations and Future Improvements
Be honest about limitations.
Possible limitations include:
•	Limited calibration data
•	Only some NAICS codes have calibrated parameters
•	POI data may be incomplete
•	Model does not include rent, zoning, parking, or demographics
•	Chatbot may not handle every wording perfectly
•	Some features may work locally but not fully in deployment
•	Scenario comparison may be limited
•	UI can still be improved
Then explain what you would improve next if you had more time.
________________________________________
10. Team Contributions
Briefly explain how the work was divided.
You may include:
•	Who worked on database integration
•	Who worked on backend/model code
•	Who worked on frontend/dashboard
•	Who worked on map
•	Who worked on chatbot
•	Who worked on UI design
•	Who worked on testing, documentation, or deployment
This does not need to be too long, but it should show that the team understands how the work came together.
________________________________________
Suggested Presentation Length
Your presentation should be clear and focused.
Suggested structure:
•	8–12 minutes presentation/demo
•	3–5 minutes questions
The exact timing may be adjusted depending on class size.
________________________________________
Suggested Slide Outline
Your team may use the following slide structure:
1.	Title slide with team name and members
2.	Problem and user scenario
3.	System overview
4.	Data and Azure SQL integration
5.	Huff model and model outputs
6.	Dashboard/UI improvements
7.	Chatbot/system improvements
8.	Demo or screenshots
9.	Limitations and future improvements
10.	Team contributions and closing
________________________________________
Presentation Evaluation Criteria
Your presentation may be evaluated based on:
•	Clear explanation of the project purpose
•	Clear explanation of the full system
•	Evidence that the system works
•	Quality of database/model integration
•	Quality of dashboard and UI improvements
•	Quality of chatbot/system improvements
•	Ability to demonstrate model runs and comparisons
•	Honest discussion of limitations
•	Team preparedness
•	Ability to answer questions
•	Professionalism and clarity of communication
________________________________________
Final Presentation Reminder
Do not only show code.
Show the decision-support experience.
A strong final presentation should help the audience understand:
•	What the user wants to decide
•	What information the system uses
•	What the model produces
•	How the dashboard presents results
•	How the chatbot supports the user
•	Why the system is useful
•	What limitations remain

10.2 Individual Final Report Instructions
The individual final report is submitted separately by each student.
Even though the project was completed in teams, each student should understand the full system. The purpose of this report is to give you an opportunity to explain the project in your own words and reflect on your own contribution and learning.
This report should not be only a list of tasks you completed. It should show that you understand how the full AI-Assisted Location Decision Support System works.
________________________________________
Suggested Report Length
Suggested length: 4–6 pages, excluding screenshots, references, or appendices.
You may include screenshots, diagrams, tables, or short code snippets if they help explain your work.
________________________________________
Required Sections
Your individual report should include the following sections.
________________________________________
1. Project Overview
Briefly describe the project.
Explain:
•	What the AI-Assisted Location Decision Support System is
•	What decision problem it supports
•	Who the intended user is
•	What the system helps the user do
Write this in your own words.
________________________________________
2. Full System Explanation
Explain how the full system works.
Your explanation should include:
•	Frontend dashboard
•	User inputs
•	Map interface
•	Chatbot interface
•	Flask backend
•	Azure SQL database
•	Huff Gravity Model
•	Model outputs
•	Results pane or visual summaries
You should explain the flow of the system.
For example:
The user enters a business category, floor area, and candidate location. The frontend sends this information to the backend. The backend checks the NAICS code, retrieves data from Azure SQL, runs the Huff model, and returns the result. The frontend then updates the map, result pane, and chatbot response.
The exact wording should be your own, based on your team’s actual system.
________________________________________
3. Data and NAICS Handling
Explain how your team’s system handles data and NAICS codes.
Your answer should address:
•	What data is stored in Azure SQL
•	Which tables are used
•	How POIs are used
•	How parameters are used
•	What happens when a NAICS code exists in the parameters table
•	What happens when a NAICS code exists in the POIs data but not in the parameters table
•	What happens when a NAICS code does not exist in the available data
You should explain the fallback logic clearly.
Reminder:
•	If NAICS exists in the parameters table, use the calibrated alpha and beta.
•	If NAICS exists in POIs but not parameters, use fallback alpha = 1 and beta = 2.
•	If NAICS does not exist in the data, the model should not produce results for that NAICS code.
________________________________________
4. Model Explanation
Explain how the Huff Gravity Model supports the decision.
You should explain:
•	What the model is trying to estimate
•	What inputs are used
•	How candidate locations and competitors are considered
•	What alpha and beta represent at a high level
•	What the model output means
•	How the user should interpret the result
You do not need to provide a highly mathematical explanation, but you should show that you understand the model logic.
________________________________________
5. UI and Dashboard Improvements
Discuss the UI improvements your team made or planned based on Module 8.
Possible topics:
•	Landing page description
•	Team name and branding
•	About Us page
•	Input labels
•	Layout
•	Map design
•	Result presentation
•	Visual hierarchy
•	User workflow
•	Reducing cognitive load
•	Making the system easier for a non-technical user
Explain why these changes matter.
________________________________________
6. System and Chatbot Improvements
Discuss the system and chatbot improvements your team made or planned based on Module 9.
Possible topics:
•	Moving map/data flow from static files to Azure SQL
•	Multiple model runs
•	Follow-up scenario handling
•	Scenario comparison
•	Business category to NAICS lookup
•	Charts or figures in the results pane
•	Plain-language chatbot responses
•	Topic control
•	Preventing invented model results
•	Communicating limitations
Explain which improvements were completed and which were still in progress.
________________________________________
7. Your Individual Contribution
Explain your personal contribution to the project.
Be specific.
Discuss:
•	What parts you worked on
•	What files, features, or tasks you contributed to
•	What problems you helped solve
•	What design or technical decisions you were involved in
•	How your work connected to the rest of the system
It is okay if you did not work on every part of the project. However, you should explain how your part fits into the overall system.
________________________________________
8. What You Learned About the Full System
Reflect on what you learned from the project.
Possible points:
•	What you learned about DSS development
•	What you learned about database-backed applications
•	What you learned about model integration
•	What you learned about chatbot behavior
•	What you learned about UI design
•	What you learned about teamwork
•	What you would do differently next time
This section should show that you understand the project beyond your assigned task.
________________________________________
9. Limitations and Future Work
Discuss limitations of your team’s system.
Possible limitations:
•	Limited data
•	Limited NAICS calibration
•	Incomplete deployment
•	Simplified model assumptions
•	Limited chatbot flexibility
•	UI limitations
•	Missing external factors such as rent, zoning, parking, or demographics
Then discuss future improvements.
Possible future improvements:
•	More complete data
•	Better model calibration
•	More advanced comparison features
•	Better chatbot memory and state handling
•	Improved visualizations
•	More robust validation
•	More user testing
•	Integration of additional decision factors
________________________________________
10. Conclusion
End with a short conclusion.
Summarize:
•	What the project achieved
•	What your team built
•	What you personally learned
•	Why this type of system can be useful for decision support
________________________________________
Individual Report Evaluation Criteria
Your individual report may be evaluated based on:
•	Clear explanation of the full system
•	Understanding of the data/model/backend/frontend/chatbot flow
•	Accurate explanation of NAICS and parameter handling
•	Clear discussion of UI and system improvements
•	Specific explanation of individual contribution
•	Thoughtful reflection on learning
•	Honest discussion of limitations
•	Clarity, organization, and professionalism
________________________________________
Important Reminder
This is an individual report.
You may discuss the same team project as your teammates, but your report should be written in your own words.
Do not simply copy the team presentation or another student’s writing.
The report should show your own understanding of the full system and your own role in the project.

Each team must submit a recorded final presentation of the AI-Assisted Location Decision Support System project.
This is a team assignment, so only one submission is required per team.
The recorded presentation should demonstrate what your team built, explain how the full system works, and show the major improvements completed during Modules 8 and 9.
________________________________________
What Your Presentation Should Include
Your presentation should cover the following areas:
1.	Team and project introduction
o	Team name
o	Team members
o	Project title
o	Short description of the DSS
2.	Problem and user scenario
o	What decision problem does your system support?
o	Who is the intended user?
o	How does the system help the user?
3.	System overview
o	Frontend dashboard
o	Map
o	Chatbot
o	Flask backend
o	Azure SQL database
o	Huff Gravity Model
o	Results pane and visual outputs
4.	Data and NAICS handling
o	How your system uses the pois, parameters, and geojson_map tables
o	How NAICS codes are handled
o	How fallback alpha and beta values are used
o	What happens when a NAICS code is not available in the data
5.	Module 8 improvements
o	UI and dashboard changes
o	Landing page improvements
o	Input clarity
o	Map design
o	Results presentation
o	Team branding and project description
6.	Module 9 improvements
o	Azure SQL-backed map/data flow
o	Multiple model runs
o	Follow-up user requests
o	Alternative location comparison
o	Business category to NAICS support
o	Charts or figures
o	Plain-language chatbot behavior
o	Topic control
o	Prevention of invented model results
7.	System demonstration
o	First model run
o	Follow-up model run
o	Comparison between locations
o	Map or results pane update
o	Chatbot explanation
o	Example of limitation handling or topic control
8.	Limitations and future improvements
o	What still needs improvement?
o	What would your team add with more time?
9.	Team contributions
o	Briefly explain how responsibilities were divided among team members
________________________________________
Presentation Length
Recommended length:
15–20 minutes
Please keep the presentation focused and organized.
________________________________________
Participation Expectation
All team members should participate in the presentation.
Team members may present different sections, but everyone should be familiar with the overall system and should contribute meaningfully to the recording.
________________________________________
Recording Options
You may record the presentation using tools such as:
•	Zoom
•	Microsoft Teams
•	PowerPoint recording
•	Google Meet
•	Canvas Studio
•	Screen recording software
•	Another similar recording tool
Your recording should include:
•	Your presentation slides
•	Clear audio
•	The video and voices of the presenters
•	A screen demonstration of the system, screenshots, or recorded demo evidence
________________________________________
Recommended Recording Process
1.	Prepare and finalize your presentation slides.
2.	Decide which team member will present each section.
3.	Practice the full presentation before recording.
4.	Open the deployed app, screenshots, or demo materials before starting.
5.	Record the presentation from beginning to end.
6.	Review the recording before submission.
7.	Confirm that the video, audio, slides, and demo are visible and understandable.
8.	Submit one presentation recording and one copy of the presentation slides per team.
________________________________________
Live Demo and Backup Evidence
A live system demonstration is recommended, but your team should prepare backup evidence in case the deployed app does not work during the recording.
Backup evidence may include:
•	Screenshots
•	A short prerecorded demo
•	Chatbot interaction examples
•	Map outputs
•	Comparison tables
•	Charts
•	Database connection evidence
•	GitHub screenshots
Do not allow a technical problem during recording to prevent your team from explaining the work completed.
________________________________________
Submission Requirements
Submit the following:
1.	Recorded presentation
2.	Final presentation slides
Only team leads should make the submission on behalf of the team.
________________________________________
Video Submission Format
Depending on the available Canvas submission settings, submit one of the following:
•	Uploaded video file
•	Canvas Studio recording
•	Shareable video link
•	Cloud storage link with viewing permission enabled
If submitting a link, confirm that anyone with the link can view the video without requesting access.
Do not submit a private link that I cannot open.
________________________________________
Suggested Video File Formats
•	A recorded presentation video, preferably .mp4 or .MOV  or
•	A narrated PowerPoint presentation in .pptx format with the audio and video recording embedded in the slides.
Please avoid unnecessarily large files when possible.
________________________________________
Slide File Types
Submit your slides as one of the following:
•	.PPT
•	.PPTX
•	.PDF
________________________________________
File Naming
Use clear file names.
Example:
TeamName_Final_Presentation.mp4
TeamName_Final_Presentation_Slides.pptx
________________________________________
Before You Submit
Confirm that:
•	The correct video was uploaded or linked
•	The video can be opened
•	The audio is clear
•	The full presentation is included
•	The slides are attached
•	All team members are listed
•	All team members participated
•	The system demo or evidence is visible
•	The link permissions are correct
________________________________________
Evaluation Criteria
The recorded team presentation may be evaluated based on:
•	Clear explanation of the project and user problem
•	Understanding of the full system
•	Quality of database and model integration
•	Quality of Module 8 UI improvements
•	Quality of Module 9 system and chatbot improvements
•	Quality of the demonstration
•	Clear discussion of NAICS handling
•	Honest discussion of limitations
•	Team participation
•	Organization and communication quality
•	Ability to explain technical and design decisions
•	Professional quality of the recording
________________________________________
Important Reminder
This is not only a slide presentation.
Your team should demonstrate and explain the decision-support system you built.
The final recording should help the audience understand:
•	What the system does
•	How it works
•	How a user interacts with it
•	How the model supports a location decision
•	What your team improved
•	What limitations remain


_____________________________________________________________________________________
Professor’s comment:
The most beautiful UI among all 5 teams.
I hope you continue developing and making your webapp better even after the class is over.
Many things I liked about the current UI but also IMPORTANT points on UI design for improvement:

- Give more credit to your team, write your team name with a large and bold font in page title section, you should be proud of your work. Create an "About US" page.
- in the results section replace "Attraction" with the competitors' current marketshare, that is important for a business owner to know if a nearby competitor has a large marketshare or not.
- reduce number of competitor to 5~10, currently it is a long list
- add a pop up of something that user knows where to click to see the results, I would make it visible for user as soon as we have the results and let user to click to hide it, I am referring to the button at top-right
- take the two boxes (competitors and runtime) next to the predicted visits and marketshare boxes, this will help remove the clutter from the chat pane
- Your chatbot should allow for the same location for comparison, because you may have alternatives in a shopping mall with different sizes, so these are the only possible comparison scenarios:
- both cases MUST have the same NAICS code
- they can have the same (x,y) or not
- they can have the same sizes or not
but they can't have both the same (x,y), size 
UI still needs some attention in making users aware of all capabilities the system has, like better demonstration of comparison and saved results

Your Github needs attention as well:
1- you need to update your repository's README.md as I explained in one of the announcements.
2-  you were supposed to disable Azure SQL migration admin route (@app.route("/admin/migrate")) in the app.py file. 
I did it for team, keeping that endpoint alive in real business applications is a fatal mistake. 
whenever you need it remove the # and run it, then when the migration is done, comment out the end point again.

