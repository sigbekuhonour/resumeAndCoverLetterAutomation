# resumeAndCoverLetterAutomation
I don't want to have to write out cover letter and resume for every job so i decided to automate it

# Resume and cover letter for job application automation  project  
  
# ++The Hybrid Architecture++  
• **The Scraper (Python):** A simple script that pulls job descriptions from a URL.  
• **The Brain (C# / .NET 9):** An API that receives the job description, talks to AI (Amazon Bedrock), and formats your resume.  
• **The Cloud (AWS):** Hosting everything so you can talk about it in your exam.  
  
  
**Weeks 1–2: The C# Foundation (Internship Prep)**  
• **Focus:** Basic syntax and Project Setup.  
• **Task:** Create an **ASP.NET Core Web API** project. Create a "Resume" class with properties like Name, Skills, and Experience.  
• **AWS Exam Link:** Learn about **Regions and Availability Zones** (where will you host this?).  
• **Commitment:** 4 hours (2 hours learning syntax, 2 hours coding the API structure).  
  
**Weeks 3–4: The Python Scraper (Speed)**  
• **Focus:** Web Scraping with **Playwright**.  
• **Task:** Write a small Python script that takes a LinkedIn or Indeed URL and extracts the "Job Description" text.  
• **Hybrid Link:** Use the Python requests library to "POST" that text to your C# API.  
• **AWS Exam Link:** Study **S3 (Storage)**. This is where you will eventually save the scraped data.  
• **Commitment:** 4 hours.  
  
**Weeks 5–6: The AI "Brain" (Amazon Bedrock)**  
• **Focus:** Generative AI in C#.  
• **Task:** Use the AWSSDK.BedrockRuntime package in your C# project. Send your "Master Resume" + the scraped job description to **Claude 3.5 Sonnet**.  
• **Result:** The AI returns 5 tailored bullet points.  
• **AWS Exam Link:** Study **IAM (Identity & Access Management)**. You’ll need to create a "User" so your code can talk to Bedrock.  
• **Commitment:** 5 hours (AI prompting can take some trial and error).  
  
**Weeks 7–8: The Cloud Deployment (Exam Prep)**  
• **Focus:** Getting it off your laptop.  
• **Task:** Deploy your C# API to **AWS App Runner** or **Lambda**.  
• **Task:** Host a simple one-page frontend (HTML/JS) on **Amazon S3** as a static website.  
• **AWS Exam Link:** Study **Shared Responsibility Model** and **Support Plans**.  
• **Commitment:** 5 hours.  
  
**Week 9: Polish & Internship Prep**  
• **Focus:** Documentation.  
• **Task:** Write a README.md for your GitHub. Explain how you used C# and AWS.  
• **Goal:** This is what you show your manager on Day 1.  
• **Commitment:** 3 hours.  
![Install NET 9 SDK &](Attachments/E677C3A5-81F2-4CA4-A115-E8C1AF05CCA4.heic)  

