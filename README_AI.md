# AI Integration — JobIntel

This document explains how the AI features in JobIntel work, which design decisions we made, and why we made them.

## What problem the AI is solving

Job descriptions are written inconsistently. One company calls it Python experience, another says Django developer, and a third writes seeking someone familiar with Flask and pandas. A simple keyword match would miss most of these connections. We needed a system that could read both the job description and a user's resume and understand that these are all talking about the same underlying skill.

On the other side, users do not know what skills they are missing or how important those skills are relative to each other. The system needs to not just find gaps but tell you which ones actually matter.

## Where AI enters the user flow

The AI pipeline runs in two places.

The first is when a new job posting is added to the database, either through the seed data on first load or when a user manually adds a posting through the search jobs page. At that point the app calls extract_job_skills, which reads the job title and description and identifies every skill present in the text.

The second is when a user uploads a resume. The app calls extract_resume_skills on the uploaded text, then immediately calls update_matches_for_resume, which compares the resume skills against every active job posting and generates a match score, a list of strengths, and a list of missing skills for each one.

The output is shown to the user on the resume detail page and the skill gaps page. The dashboard also pulls from these results to generate the AI insight feed.

## How the skill extraction works

We built a custom NLP pipeline rather than calling an external API. The pipeline is defined in services.py.

We maintain a skill ontology, which is a list of about 20 skills each with a set of aliases. For example the Python entry includes the aliases python, django, flask, pandas, and numpy. The logic is that if any of these words appear in a text, we count it as evidence of Python skills.

When we extract skills from a text, we normalise the whole thing to lowercase and then run a regex word boundary search for each alias. We use word boundaries so that a mention of pythonic does not accidentally match python, and so that s3 only matches the full token and not any word that contains s3 as a substring. If one or more aliases match, we create a skill record with the matched aliases stored as evidence.

For job postings we also look at the surrounding context of each match. If the alias appears within about 90 characters of a phrase like required skills or must have, we mark that skill as required rather than just mentioned. This distinction affects the match score weighting.

## How the match scoring works

The match score is a weighted overlap between the skills on a resume and the skills required by a job posting.

Each job skill gets a weight. Required skills get a weight of 1.5, preferred skills get 1.2, and mentioned skills get 1.0. We add up the weights of all job skills to get a total, then add up the weights of only the skills that also appear on the resume to get a matched total. The score is matched divided by total multiplied by 100, rounded to two decimal places.

This means a resume that has all the required skills but none of the preferred ones will still score reasonably well. And a resume that is missing a required skill is penalised more than one that is missing a skill that was only mentioned in passing.

Skills that are present in the job but absent from the resume become SkillGap records. If the overall match score is below 60, those gaps are marked high priority. Otherwise they are marked medium priority.

## Model selection and design decisions

We chose not to use a large language model API for the core pipeline. The main reason is cost and control. If every resume upload triggered an API call to something like OpenAI, the cost would scale directly with the number of users and uploads. Running 100 resume-to-job comparisons would mean 100 API calls per upload. With 4 sample jobs in the database that is already 4 calls per upload, and as the job database grows that number grows with it.

Our approach runs entirely in Python with no external dependencies beyond Django and the standard library. Every extraction and scoring step is deterministic and free to run. The tradeoff is that our ontology is fixed at the skills we defined. A job description that mentions an obscure framework we did not include will not be detected. But for the most common technical skills relevant to the roles we are targeting, the coverage is good.

We also considered using sentence-transformers to embed job descriptions and resumes and compute cosine similarity scores. This would give us semantic matching, meaning a resume that says I built REST services would match a job that says API development experience required even if neither uses the exact same keywords. We decided not to implement this in the current version because it adds a model dependency and inference time to every upload, and we wanted to make sure the core workflow was solid first. We document it as a future improvement.

## What an API-only version would look like

If we had used an external API like the OpenAI API for all of this, the flow would be something like: send the resume text and job description to GPT-4 in a single prompt, ask it to return a structured JSON object with a match score and list of missing skills. This would probably give better results on edge cases because a large language model understands context and synonyms better than our regex patterns.

But the downsides are significant. First, cost. At current pricing, a single pair comparison of a full resume against a full job description could use several thousand tokens. If a user uploads a resume and we compare it against 50 stored jobs, that is 50 API calls, which adds up quickly especially in a classroom or demo setting where multiple people are using the app simultaneously. Second, latency. Each API call takes a few seconds, so a single resume upload would trigger a long wait. Our current approach runs all comparisons in under a second locally. Third, we would have no control over what the model considers a skill, how it weighs importance, or what format it returns. Our weighted scoring logic gives us full control over the grading behaviour.

Our current design is cheaper, faster, and more predictable. The tradeoff is lower accuracy on unusual or creative job descriptions.

## Guardrails and failure handling

If a user uploads a file that is not a plain text file, the extract_text_from_upload function returns an empty string. The resume is still saved but no skills are extracted and no matches are generated. The user sees a message that the upload was successful, and the resume appears in their list. They can still view it, but the match score will be zero because there are no skills to compare.

If the database has no job postings, update_matches_for_resume runs over an empty queryset and returns an empty list. No errors are thrown and the user simply sees no match results until job data is available.

If the extracted text mentions no skills that appear in our ontology, the resume is saved with no ResumeSkill records. The match score against every job will be zero and every job skill will be listed as missing. This is technically correct behaviour, not a failure, since the resume genuinely did not mention any of the tracked skills.