# JobIntel

JobIntel is a web application that helps job seekers understand the current job market. Instead of reading through dozens of job postings manually, users can upload their resume and the app compares their skills against stored job descriptions, shows them where they are strong, and points out the skills they are missing. It also shows market-wide trends like which skills appear most often across all postings.

We built this as our IS490 final project at the University of Illinois Urbana-Champaign.

## Team

- Blake Mackin
- Swarnika Bhardwaj
- Tony Chan
- Aidan Gilbert

## What the app does

When you log in, the dashboard shows you the top skills appearing across all stored job postings and a feed of AI-generated insights about the market. You can search for jobs using keywords or filters, save roles you are interested in, and upload your resume as a plain text file. Once your resume is uploaded, the app extracts the skills mentioned in it and compares them against every stored job posting to generate a match score and a list of skill gaps. The analytics page shows trend data for each skill over time.

## Requirements

- Python 3.11 or higher
- pip

All Python dependencies are listed in requirements.txt.

## Setup

Clone the repository and move into the project folder.

```
git clone https://github.com/Blake9000/IS490-Final-Project.git
cd IS490-Final-Project
```

Create and activate a virtual environment.

```
python -m venv venv
source venv/bin/activate        # on Mac or Linux
venv\Scripts\activate           # on Windows
```

Install dependencies.

```
pip install -r requirements.txt
```

Apply database migrations.

```
python manage.py migrate
```

Create a superuser account so you can log in and access the admin panel.

```
python manage.py createsuperuser
```

Run the development server.

```
python manage.py runserver
```

Open your browser and go to http://127.0.0.1:8000 to see the app.

The Django admin panel is at http://127.0.0.1:8000/admin and lets you add job postings, inspect matches, and manage all data manually.

The first time the dashboard loads, the app automatically seeds the database with reference skills and a few sample job postings so there is something to look at right away.

## Environment variables

Copy the example env file and fill in your values before running in any non-development context.

```
cp .env.example .env
```

The app reads SECRET_KEY and DEBUG from environment variables using python-decouple. Do not commit your .env file. It is listed in .gitignore.

## Internal API endpoints

The app exposes three read-only JSON endpoints that do not require authentication.

```
GET /api/skills/          returns top in-demand skills with demand percentage
GET /api/jobs/            returns active job postings, supports ?q= and filter params
GET /api/trends/          returns skill trend snapshot data for the past 30 days
```

Two CSV export endpoints require you to be logged in.

```
GET /export/matches/      downloads your resume-to-job match results as a CSV file
GET /export/skill-gaps/   downloads your skill gaps across all matches as a CSV file
```

## Where the AI feature lives

The AI feature is built into the resume upload flow. The full explanation of the AI design is in README_AI.md.

## Running tests

```
python manage.py test resume_fixer
```