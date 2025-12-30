# import json
# import re
# import shutil
# from datetime import datetime
# import os
# import subprocess
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from langchain_ollama import ChatOllama
# from langchain_core.messages import SystemMessage
# from langchain_community.tools import DuckDuckGoSearchRun

# app = FastAPI()


# APPLICATIONS_FILE = "applications.json"
# ARCHIVE_DIR = "archives"
# # Standardized Paths
# TEMPLATE_PATH = "template.tex"
# RESUME_TEX = "tailored_resume.tex"
# RESUME_PDF = "tailored_resume.pdf"
# INFO_TEX = "info.tex"
# BODY_TEX = "body.tex"
# MAIN_TEX = "main.tex"
# CL_PDF = "cover_letter.pdf"

# search = DuckDuckGoSearchRun()

# if not os.path.exists(ARCHIVE_DIR):
#     os.makedirs(ARCHIVE_DIR)

# class JobInput(BaseModel):
#     jd: str

# class SaveInput(BaseModel):
#     draft: dict

# class CLInput(BaseModel):
#     jd: str
#     resume_draft: dict
#     company: str

# class FinalizeInput(BaseModel):
#     company: str
#     position: str
#     jd: str
#     resume_path: str = RESUME_PDF
#     cl_path: str = CL_PDF

# class StatusUpdate(BaseModel):
#     index: int
#     new_status: str


# def clean_latex(text):
#     if not isinstance(text, str): return ""
#     replacements = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
#     for char, replacement in replacements.items():
#         text = re.sub(f"(?<!\\\\){re.escape(char)}", replacement, text)
#     return text

# def inject_into_latex(draft):
#     with open(TEMPLATE_PATH, "r") as f:
#         content = f.read()

#     def replace_section(section_name, new_content, full_text):
#         pattern = r"(\\begin\{rSection\}\{" + re.escape(section_name) + r"\})(.*?)(\\end\{rSection\})"
#         match = re.search(pattern, full_text, flags=re.DOTALL)
#         if match:
#             return full_text[:match.start()] + f"{match.group(1)}\n{new_content}\n{match.group(3)}" + full_text[match.end():]
#         return full_text

#     # Inject cleaned strings
#     for section in ["Summary", "Skills", "Experience", "Projects"]:
#         content = replace_section(section, clean_latex(draft.get(section.lower(), '')), content)

#     with open(RESUME_TEX, "w") as f:
#         f.write(content)

# def load_apps():
#     """Helper to safely load the applications list."""
#     if not os.path.exists(APPLICATIONS_FILE) or os.stat(APPLICATIONS_FILE).st_size == 0:
#         return []
#     try:
#         with open(APPLICATIONS_FILE, "r") as f:
#             return json.load(f)
#     except json.JSONDecodeError:
#         return []

# def run_compilation(tex_file):
#     """Runs pdflatex and returns success status."""
#     result = subprocess.run(
#         ["pdflatex", "-interaction=nonstopmode", tex_file], 
#         capture_output=True, 
#         text=True
#     )
#     return result.returncode == 0

# @app.post("/generate-resume")
# async def generate(input_data: JobInput):
#     with open("master_resume.json", "r") as f:
#         master_resume = json.load(f)

#     llm = ChatOllama(model="qwen3:30b", temperature=0.1)
#     prompt = f"""
#     You are a LaTeX Expert. Based on this Master Resume: {json.dumps(master_resume)}
#     And this Job Description: {input_data.jd}
#     Return ONLY a JSON object. 
#     Values must be valid LaTeX STRINGS. Use \\item for bullet points.
#     Expected Keys: "skills", "experience", "projects", "summary"
#     """
#     try:
#         response = llm.invoke([SystemMessage(content=prompt)])
#         content = response.content.replace("```json", "").replace("```", "").strip()
#         draft = json.loads(content)
        
#         # --- NEW LOGIC: Auto-compile on generation ---
#         inject_into_latex(draft)
#         run_compilation(RESUME_TEX)
#         # ----------------------------------------------
        
#         return draft
#     except Exception as e:
#         return {"summary": "Error", "experience": "", "skills": "", "projects": ""}
    

# @app.post("/save-resume")
# async def save(data: SaveInput):
#     inject_into_latex(data.draft)
#     return {"status": "success"}

# @app.post("/compile-resume")
# async def compile_res():
#     # Update this to use the helper
#     success = run_compilation(RESUME_TEX)
#     return {"status": "success" if success else "error"}


# @app.post("/generate-cover-letter")
# async def generate_cl(input_data: CLInput):
#     try:
#         research = search.run(f"Recent news and values of {input_data.company} 2025")
#     except:
#         research = "Professional company."

#     llm = ChatOllama(model="qwen3:30b", temperature=0.1)
#     prompt = f"""
#     Write a cover letter body in LaTeX. 
#     Company: {input_data.company} | Research: {research}
#     Resume: {json.dumps(input_data.resume_draft)}

#     Return JSON: {{"body": " Normal text", "info": {{"street": "", "city": "", "state": "", "zip": "", "recipient": ""}}}}
#     """
#     try:
#         response = llm.invoke([SystemMessage(content=prompt)])
#         res_data = json.loads(response.content.replace("```json", "").replace("```", ""))
#     except Exception as e:
#         res_data = {
#             "body": "Error generating cover letter. Please try again.",
#             "info": {"street": "", "city": "", "state": "", "zip": "", "recipient": ""}
#         }

#     # Write info.tex
#     with open(INFO_TEX, "w") as f:
#         f.write(f"\\newcommand{{\\myname}}{{{input_data.resume_draft.get('name', 'Applicant')}}}\n")
#         f.write(f"\\newcommand{{\\myemail}}{{{input_data.resume_draft.get('email', 'email@example.com')}}}\n")
#         f.write(f"\\newcommand{{\\myphone}}{{{input_data.resume_draft.get('phone', '000-000-0000')}}}\n")
#         f.write(f"\\newcommand{{\\company}}{{{input_data.company}}}\n")
#         f.write(f"\\newcommand{{\\recipient}}{{{res_data['info'].get('recipient', 'Hiring Manager')}}}\n")
#         f.write(f"\\newcommand{{\\street}}{{{res_data['info'].get('street', '123 Tech Way')}}}\n")
#         f.write(f"\\newcommand{{\\city}}{{{res_data['info'].get('city', 'City')}}}\n")
#         f.write(f"\\newcommand{{\\state}}{{{res_data['info'].get('state', 'Province')}}}\n")
#         f.write(f"\\newcommand{{\\zip}}{{{res_data['info'].get('zip', 'M5V 2L7')}}}\n")
#         # Add missing commands for your template
#         f.write("\\newcommand{\\mytitle}{Data Engineer}\n\\newcommand{\\greeting}{Dear}\n\\newcommand{\\closer}{Sincerely}\n")

#     with open(BODY_TEX, "w") as f:
#         f.write(clean_latex(res_data['body']))

#     subprocess.run(["pdflatex", "-interaction=nonstopmode", MAIN_TEX])
#     if os.path.exists("main.pdf"): os.replace("main.pdf", CL_PDF)
    
#     return {"letter_text": res_data['body']}

# @app.post("/finalize-application")
# async def finalize(data: FinalizeInput):
#     date_str = datetime.now().strftime("%Y-%m-%d")
#     safe_company = re.sub(r'\W+', '', data.company)
#     safe_pos = re.sub(r'\W+', '', data.position)
#     folder_name = f"{date_str}_{safe_pos}_{safe_company}"
#     folder_path = os.path.join(ARCHIVE_DIR, folder_name)
    
#     os.makedirs(folder_path, exist_ok=True)

#     base_name = f"{date_str}_{safe_pos}_{safe_company}"
#     jd_file = f"{base_name}_JD.txt"
#     res_file = f"{base_name}_Resume.pdf"
#     cl_file = f"{base_name}_coverletter.pdf"

#     # Save Files
#     with open(os.path.join(folder_path, jd_file), "w") as f:
#         f.write(data.jd)
    
#     if os.path.exists(RESUME_PDF):
#         shutil.copy(RESUME_PDF, os.path.join(folder_path, res_file))
#     if os.path.exists(CL_PDF):
#         shutil.copy(CL_PDF, os.path.join(folder_path, cl_file))

#     # Safely load and update
#     apps = load_apps()
#     apps.append({
#         "date": date_str,
#         "company": data.company,
#         "position": data.position,
#         "status": "Applied",
#         "folder": folder_path,
#         "jd_file": jd_file,
#         "res_file": res_file,
#         "cl_file": cl_file
#     })

#     with open(APPLICATIONS_FILE, "w") as f:
#         json.dump(apps, f, indent=4)

#     return {"status": "success"}

# @app.get("/get-applications")
# async def get_apps():
#     return load_apps()

# @app.post("/update-status")
# async def update_status(data: StatusUpdate):
#     apps = load_apps()
#     if 0 <= data.index < len(apps):
#         apps[data.index]["status"] = data.new_status
#         with open(APPLICATIONS_FILE, "w") as f:
#             json.dump(apps, f, indent=4)
#         return {"status": "updated"}
#     raise HTTPException(status_code=400, detail="Invalid index")

# import json
# import re
# import shutil
# from datetime import datetime
# import os
# import subprocess
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from langchain_ollama import ChatOllama
# from langchain_core.messages import SystemMessage
# from langchain_community.tools import DuckDuckGoSearchRun

# app = FastAPI()


# APPLICATIONS_FILE = "applications.json"
# ARCHIVE_DIR = "archives"
# # Standardized Paths
# TEMPLATE_PATH = "template.tex"
# RESUME_TEX = "tailored_resume.tex"
# RESUME_PDF = "tailored_resume.pdf"
# INFO_TEX = "info.tex"
# BODY_TEX = "body.tex"
# MAIN_TEX = "main.tex"
# CL_PDF = "cover_letter.pdf"

# search = DuckDuckGoSearchRun()

# if not os.path.exists(ARCHIVE_DIR):
#     os.makedirs(ARCHIVE_DIR)

# class JobInput(BaseModel):
#     jd: str

# class SaveInput(BaseModel):
#     draft: dict

# class CLInput(BaseModel):
#     jd: str
#     resume_draft: dict
#     company: str

# class SaveCLInput(BaseModel):
#     body: str
#     company: str
#     resume_draft: dict

# class FinalizeInput(BaseModel):
#     company: str
#     position: str
#     jd: str
#     resume_path: str = RESUME_PDF
#     cl_path: str = CL_PDF

# class StatusUpdate(BaseModel):
#     index: int
#     new_status: str


# def clean_latex(text):
#     if not isinstance(text, str): return ""
#     replacements = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
#     for char, replacement in replacements.items():
#         text = re.sub(f"(?<!\\\\){re.escape(char)}", replacement, text)
#     return text

# def inject_into_latex(draft):
#     with open(TEMPLATE_PATH, "r") as f:
#         content = f.read()

#     def replace_section(section_name, new_content, full_text):
#         pattern = r"(\\begin\{rSection\}\{" + re.escape(section_name) + r"\})(.*?)(\\end\{rSection\})"
#         match = re.search(pattern, full_text, flags=re.DOTALL)
#         if match:
#             return full_text[:match.start()] + f"{match.group(1)}\n{new_content}\n{match.group(3)}" + full_text[match.end():]
#         return full_text

#     # Inject cleaned strings
#     for section in ["Summary", "Skills", "Experience", "Projects"]:
#         content = replace_section(section, clean_latex(draft.get(section.lower(), '')), content)

#     with open(RESUME_TEX, "w") as f:
#         f.write(content)

# def save_cover_letter_files(body_text, company, resume_draft):
#     """Helper function to save cover letter .tex files and compile"""
#     # Write info.tex with all required commands
#     with open(INFO_TEX, "w") as f:
#         f.write(f"\\newcommand{{\\myname}}{{{resume_draft.get('name', 'Applicant')}}}\n")
#         f.write(f"\\newcommand{{\\myemail}}{{{resume_draft.get('email', 'email@example.com')}}}\n")
#         f.write(f"\\newcommand{{\\myphone}}{{{resume_draft.get('phone', '000-000-0000')}}}\n")
#         f.write(f"\\newcommand{{\\company}}{{{company}}}\n")
#         f.write(f"\\newcommand{{\\recipient}}{{Hiring Manager}}\n")
#         f.write(f"\\newcommand{{\\street}}{{123 Tech Way}}\n")
#         f.write(f"\\newcommand{{\\city}}{{City}}\n")
#         f.write(f"\\newcommand{{\\state}}{{Province}}\n")
#         f.write(f"\\newcommand{{\\zip}}{{M5V 2L7}}\n")
#         f.write("\\newcommand{\\mytitle}{Data Engineer}\n")
#         f.write("\\newcommand{\\greeting}{Dear}\n")
#         f.write("\\newcommand{\\closer}{Sincerely}\n")

#     # Write body.tex with cleaned text
#     with open(BODY_TEX, "w") as f:
#         f.write(clean_latex(body_text))

# def load_apps():
#     """Helper to safely load the applications list."""
#     if not os.path.exists(APPLICATIONS_FILE) or os.stat(APPLICATIONS_FILE).st_size == 0:
#         return []
#     try:
#         with open(APPLICATIONS_FILE, "r") as f:
#             return json.load(f)
#     except json.JSONDecodeError:
#         return []

# def run_compilation(tex_file):
#     """Runs pdflatex and returns success status."""
#     result = subprocess.run(
#         ["pdflatex", "-interaction=nonstopmode", tex_file], 
#         capture_output=True, 
#         text=True
#     )
#     return result.returncode == 0

# @app.post("/generate-resume")
# async def generate(input_data: JobInput):
#     with open("master_resume.json", "r") as f:
#         master_resume = json.load(f)

#     llm = ChatOllama(model="qwen3:30b", temperature=0.1)
#     prompt = f"""
#     You are a LaTeX Expert. Based on this Master Resume: {json.dumps(master_resume)}
#     And this Job Description: {input_data.jd}
#     Return ONLY a JSON object. 
#     Values must be valid LaTeX STRINGS. Use \\item for bullet points.
#     Expected Keys: "skills", "experience", "projects", "summary"
#     """
#     try:
#         response = llm.invoke([SystemMessage(content=prompt)])
#         content = response.content.replace("```json", "").replace("```", "").strip()
#         draft = json.loads(content)
        
#         # Auto-compile on generation
#         inject_into_latex(draft)
#         run_compilation(RESUME_TEX)
        
#         return draft
#     except Exception as e:
#         return {"summary": "Error", "experience": "", "skills": "", "projects": ""}
    
    
# @app.post("/save-resume")
# async def save(data: SaveInput):
#     inject_into_latex(data.draft)
#     return {"status": "success"}

# @app.post("/compile-resume")
# async def compile_res():
#     success = run_compilation(RESUME_TEX)
#     return {"status": "success" if success else "error"}


# @app.post("/generate-cover-letter")
# async def generate_cl(input_data: CLInput):
#     try:
#         research = search.run(f"Recent news and values of {input_data.company} 2025")
#     except:
#         research = "Professional company."

#     llm = ChatOllama(model="qwen3:30b", temperature=0.1)
#     prompt = f"""
#     Write a cover letter body in LaTeX. 
#     Company: {input_data.company} | Research: {research}
#     Resume: {json.dumps(input_data.resume_draft)}

#     Return JSON: {{"body": "Normal text", "info": {{"street": "", "city": "", "state": "", "zip": "", "recipient": ""}}}}
#     """
#     try:
#         response = llm.invoke([SystemMessage(content=prompt)])
#         res_data = json.loads(response.content.replace("```json", "").replace("```", ""))
#     except Exception as e:
#         res_data = {
#             "body": "Error generating cover letter. Please try again.",
#             "info": {"street": "", "city": "", "state": "", "zip": "", "recipient": ""}
#         }

#     # Save files using helper function
#     save_cover_letter_files(res_data['body'], input_data.company, input_data.resume_draft)
    
#     # Compile
#     subprocess.run(["pdflatex", "-interaction=nonstopmode", MAIN_TEX])
#     if os.path.exists("main.pdf"): 
#         os.replace("main.pdf", CL_PDF)
    
#     return {"letter_text": res_data['body']}


# @app.post("/save-cover-letter")
# async def save_cl(data: SaveCLInput):
#     """Save edited cover letter text and recompile without regenerating"""
#     # Save the edited body text to files
#     save_cover_letter_files(data.body, data.company, data.resume_draft)
    
#     # Compile to PDF
#     result = subprocess.run(
#         ["pdflatex", "-interaction=nonstopmode", MAIN_TEX],
#         capture_output=True,
#         text=True
#     )
    
#     # Move compiled PDF to correct location
#     if os.path.exists("main.pdf"):
#         os.replace("main.pdf", CL_PDF)
    
#     return {
#         "status": "success" if result.returncode == 0 else "error",
#         "message": "Cover letter updated and compiled"
#     }


# @app.post("/finalize-application")
# async def finalize(data: FinalizeInput):
#     date_str = datetime.now().strftime("%Y-%m-%d")
#     safe_company = re.sub(r'\W+', '', data.company)
#     safe_pos = re.sub(r'\W+', '', data.position)
#     folder_name = f"{date_str}_{safe_pos}_{safe_company}"
#     folder_path = os.path.join(ARCHIVE_DIR, folder_name)
    
#     os.makedirs(folder_path, exist_ok=True)

#     base_name = f"{date_str}_{safe_pos}_{safe_company}"
#     jd_file = f"{base_name}_JD.txt"
#     res_file = f"{base_name}_Resume.pdf"
#     cl_file = f"{base_name}_coverletter.pdf"

#     # Save Files
#     with open(os.path.join(folder_path, jd_file), "w") as f:
#         f.write(data.jd)
    
#     if os.path.exists(RESUME_PDF):
#         shutil.copy(RESUME_PDF, os.path.join(folder_path, res_file))
#     if os.path.exists(CL_PDF):
#         shutil.copy(CL_PDF, os.path.join(folder_path, cl_file))

#     # Safely load and update
#     apps = load_apps()
#     apps.append({
#         "date": date_str,
#         "company": data.company,
#         "position": data.position,
#         "status": "Applied",
#         "folder": folder_path,
#         "jd_file": jd_file,
#         "res_file": res_file,
#         "cl_file": cl_file
#     })

#     with open(APPLICATIONS_FILE, "w") as f:
#         json.dump(apps, f, indent=4)

#     return {"status": "success"}

# @app.get("/get-applications")
# async def get_apps():
#     return load_apps()

# @app.post("/update-status")
# async def update_status(data: StatusUpdate):
#     apps = load_apps()
#     if 0 <= data.index < len(apps):
#         apps[data.index]["status"] = data.new_status
#         with open(APPLICATIONS_FILE, "w") as f:
#             json.dump(apps, f, indent=4)
#         return {"status": "updated"}
#     raise HTTPException(status_code=400, detail="Invalid index")

import json
import re
import shutil
from datetime import datetime
import os
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langchain_community.tools import DuckDuckGoSearchRun

app = FastAPI()


APPLICATIONS_FILE = "applications.json"
ARCHIVE_DIR = "archives"
# Standardized Paths
TEMPLATE_PATH = "template.tex"
RESUME_TEX = "tailored_resume.tex"
RESUME_PDF = "tailored_resume.pdf"
INFO_TEX = "info.tex"
BODY_TEX = "body.tex"
MAIN_TEX = "main.tex"
CL_PDF = "cover_letter.pdf"

search = DuckDuckGoSearchRun()

if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR)

class JobInput(BaseModel):
    jd: str

class SaveInput(BaseModel):
    draft: dict

class CLInput(BaseModel):
    jd: str
    resume_draft: dict
    company: str

class SaveCLInput(BaseModel):
    body: str
    company: str
    resume_draft: dict

class FinalizeInput(BaseModel):
    company: str
    position: str
    jd: str
    resume_path: str = RESUME_PDF
    cl_path: str = CL_PDF

class StatusUpdate(BaseModel):
    index: int
    new_status: str


def clean_latex(text):
    """Escape special LaTeX characters, but preserve existing LaTeX commands"""
    if not isinstance(text, str): 
        return ""
    
    # Don't escape if it's already a LaTeX command
    # Only escape literal characters that aren't part of LaTeX syntax
    result = text
    
    # Replace special characters but avoid already escaped ones
    replacements = [
        (r'(?<!\\)&', r'\&'),
        (r'(?<!\\)%', r'\%'),
        (r'(?<!\\)\$', r'\$'),
        (r'(?<!\\)#', r'\#'),
    ]
    
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    
    return result

def inject_into_latex(draft):
    """Inject resume sections into the exact template schema"""
    with open(TEMPLATE_PATH, "r") as f:
        content = f.read()

    def replace_section(section_name, new_content, full_text):
        # Find the section and replace everything between begin and end
        pattern = r'(\\begin\{rSection\}\{' + re.escape(section_name) + r'\})(.*?)(\\end\{rSection\})'
        match = re.search(pattern, full_text, flags=re.DOTALL)
        if match:
            # Preserve the vspace if it exists in original
            vspace_line = "\n\\vspace{0.8em}\n" if section_name != "Summary" else "\n\\vspace{0.4em}\n"
            new_section = f"\\begin{{rSection}}{{{section_name}}}{vspace_line}{new_content}\n\\end{{rSection}}"
            return full_text[:match.start()] + new_section + full_text[match.end():]
        return full_text

    # Inject content - DON'T escape LaTeX in the content since it's already formatted
    content = replace_section("Summary", draft.get('summary', ''), content)
    content = replace_section("Skills", draft.get('skills', ''), content)
    content = replace_section("Experience", draft.get('experience', ''), content)
    content = replace_section("Projects", draft.get('projects', ''), content)

    with open(RESUME_TEX, "w", encoding='utf-8') as f:
        f.write(content)

def save_cover_letter_files(body_text, company, resume_draft):
    """Helper function to save cover letter .tex files and compile"""
    with open(INFO_TEX, "w") as f:
        f.write(f"\\newcommand{{\\myname}}{{Jon Doe}}\n")
        f.write(f"\\newcommand{{\\myemail}}{{jondoe@gmail.com}}\n")
        f.write(f"\\newcommand{{\\myphone}}{{(647) 123-4567}}\n")
        f.write(f"\\newcommand{{\\company}}{{{clean_latex(company)}}}\n")
        f.write(f"\\newcommand{{\\recipient}}{{Hiring Manager}}\n")
        f.write(f"\\newcommand{{\\street}}{{123 Tech Way}}\n")
        f.write(f"\\newcommand{{\\city}}{{Toronto}}\n")
        f.write(f"\\newcommand{{\\state}}{{ON}}\n")
        f.write(f"\\newcommand{{\\zip}}{{M5V 2L7}}\n")
        f.write("\\newcommand{\\mytitle}{Data Engineer}\n")
        f.write("\\newcommand{\\greeting}{Dear}\n")
        f.write("\\newcommand{\\closer}{Sincerely}\n")

    with open(BODY_TEX, "w") as f:
        f.write(clean_latex(body_text))

def load_apps():
    """Helper to safely load the applications list."""
    if not os.path.exists(APPLICATIONS_FILE) or os.stat(APPLICATIONS_FILE).st_size == 0:
        return []
    try:
        with open(APPLICATIONS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def run_compilation(tex_file):
    """Runs pdflatex and returns success status."""
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", tex_file], 
        capture_output=True, 
        text=True,
        cwd=os.getcwd()
    )
    return result.returncode == 0

@app.post("/generate-resume")
async def generate(input_data: JobInput):
    with open("master_resume.json", "r") as f:
        master_resume = json.load(f)

    llm = ChatOllama(model="qwen3:30b", temperature=0.1)
    
    prompt = f"""
You are an expert resume tailoring assistant. Your task is to customize a master resume for a specific job description.

MASTER RESUME DATA:
{json.dumps(master_resume, indent=2)}

TARGET JOB DESCRIPTION:
{input_data.jd}

OUTPUT REQUIREMENTS:
Generate a JSON object with these exact keys: "summary", "skills", "experience", "projects"

Each value should be a string containing properly formatted LaTeX code following these EXACT patterns:

1. SUMMARY (single paragraph):
Example:
"Data Engineering Consultant with 2+ years' experience building ETL pipelines, cloud data solutions, and BI dashboards across Azure. Skilled in Python, SQL, and Power BI, translating complex data into actionable marketing and business insights."

2. SKILLS (category format with double backslash line breaks):
Example:
"\\textbf{{Databases \\& SQL:}} SQL Server, Oracle, Snowflake, Azure Data Factory \\\\
\\textbf{{Programming:}} Python (pandas, matplotlib), Bash/Shell, Java \\\\
\\textbf{{Cloud \\& ETL:}} GCP, Databricks, Microsoft Azure, SSRS \\\\
\\textbf{{Other:}} Agile/Scrum, Stakeholder Engagement"

CRITICAL: 
- Use \\& for ampersands in skill categories
- End each skill line with \\\\ (double backslash)
- Last line should NOT have \\\\

3. EXPERIENCE (job entries with bullets):
Example:
"\\textbf{{AI Engineering Intern, Toronto Business College, Toronto, ON}} \\hfill Jan 2025 – Apr 2025

\\begin{{itemize}}
    \\item Led the design and deployment of AI meeting assistant reducing manual time by 70\\%.
    \\item Translated business context into ML workflows integrating Whisper and Mistral models.
    \\item Applied statistical testing to validate model outputs through versioned CI/CD pipelines.
\\end{{itemize}}

\\textbf{{Associate Consultant, TekLink Software, Hyderabad, India}} \\hfill Jul 2022 – Aug 2023
\\begin{{itemize}}
    \\item Designed ETL pipelines in Azure Data Factory integrating financial data.
    \\item Developed SQL stored procedures improving compliance accuracy by 18\\%.
\\end{{itemize}}"

CRITICAL:
- Use \\textbf for job titles
- Use \\hfill for date alignment  
- Leave blank line between title and \\begin{{itemize}}
- Use proper itemize environment with \\item
- Leave blank line between jobs

4. PROJECTS (one-liner format):
Example:
"\\textbf{{Distributed Recommender System (GCP)}} – Designed scalable recommendation engine using Spark on GCP Dataproc.

\\textbf{{Meeting Intelligence Assistant}} – Built RAG pipeline with Whisper + Mistral-7B for meeting transcription.

\\textbf{{Emotional Intelligence Chatbot}} – Developed agentic chatbot using LangChain + FAISS."

CRITICAL:
- Use \\textbf for project names
- Use – (en dash) after project name
- Leave blank line between projects

IMPORTANT RULES:
- Focus on content most relevant to the target job
- Use concrete metrics and technologies
- Keep LaTeX syntax exactly as shown in examples
- Escape ampersands as \\& 
- Use proper spacing and line breaks
- Include 4-6 bullets per job
- Include 4-5 projects

Make it in a way that after all combined it creates a minimum 95 ATS Score.
Return ONLY the JSON object with no markdown formatting, no code blocks, no explanations.

"""
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        content = response.content.replace("```json", "").replace("```", "").strip()
        
        # Try to extract JSON if there's extra text
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()
        
        draft = json.loads(content)
        
        # Validate required keys
        required_keys = ["summary", "skills", "experience", "projects"]
        for key in required_keys:
            if key not in draft:
                draft[key] = ""
        
        print(f"Generated draft summary: {draft.get('summary', '')[:100]}...")
        
        # Inject and compile
        inject_into_latex(draft)
        compilation_success = run_compilation(RESUME_TEX)
        
        # Clean up auxiliary files
        for ext in ['.aux', '.log', '.out']:
            aux_file = RESUME_TEX.replace('.tex', ext)
            if os.path.exists(aux_file):
                try:
                    os.remove(aux_file)
                except:
                    pass
        
        if not compilation_success:
            print("WARNING: PDF compilation failed")
            # Read log file for debugging
            log_file = RESUME_TEX.replace('.tex', '.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    print(f"LaTeX log: {f.read()[-500:]}")  # Last 500 chars
        
        return draft
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Received content: {content[:200]}...")
        # Return fallback
        return {
            "summary": "Data Engineering professional with experience in ETL pipelines, cloud solutions, and analytics.",
            "skills": "\\textbf{Programming:} Python, SQL \\\\\\n\\textbf{Cloud:} Azure, AWS \\\\\\n\\textbf{Tools:} Databricks, Power BI",
            "experience": "\\textbf{Data Engineer, Company, Location} \\hfill Jan 2020 – Present\\n\\n\\begin{itemize}\\n    \\item Built ETL pipelines processing large datasets\\n    \\item Developed dashboards for business insights\\n\\end{itemize}",
            "projects": "\\textbf{Data Pipeline Project} – Built scalable ETL solution using Python and Spark.\\n\\n\\textbf{Analytics Dashboard} – Created interactive BI dashboard with Power BI."
        }
    except Exception as e:
        print(f"Error in generate: {e}")
        import traceback
        traceback.print_exc()
        return {
            "summary": "Experienced data professional.",
            "skills": "\\textbf{Technical:} Python, SQL",
            "experience": "\\textbf{Role, Company, Location} \\hfill Date\\n\\n\\begin{itemize}\\n    \\item Key achievement\\n\\end{itemize}",
            "projects": "\\textbf{Project} – Description."
        }
    
    
@app.post("/save-resume")
async def save(data: SaveInput):
    inject_into_latex(data.draft)
    return {"status": "success"}

@app.post("/compile-resume")
async def compile_res():
    """Compile the resume .tex file to PDF"""
    if not os.path.exists(RESUME_TEX):
        return {"status": "error", "message": "Resume .tex file not found"}
    
    success = run_compilation(RESUME_TEX)
    
    # Clean up auxiliary files
    for ext in ['.aux', '.log', '.out']:
        aux_file = RESUME_TEX.replace('.tex', ext)
        if os.path.exists(aux_file):
            try:
                os.remove(aux_file)
            except:
                pass
    
    pdf_exists = os.path.exists(RESUME_PDF)
    
    return {
        "status": "success" if success and pdf_exists else "error",
        "message": "Compilation successful" if success else "Compilation failed",
        "pdf_created": pdf_exists
    }


@app.post("/generate-cover-letter")
async def generate_cl(input_data: CLInput):
    try:
        research = search.run(f"Recent news and values of {input_data.company} 2025")
    except:
        research = "Professional company with strong industry reputation."

    llm = ChatOllama(model="qwen3:30b", temperature=0.1)
    
    prompt = f"""
Write a professional cover letter body for given position.
You are an expert Cover letter writer. Write a cover letter for me ensuring the following:

⁠1. The cover letter should be unique and industry friendly and ⁠include numbers and relevant skills.
2. Opening: Express enthusiasm and mention specific company attributes from research
⁠2.1. It should showcase two or three of my best experiences relevant to the role.
3. It should not have biases/ opinions but only industry best practices
4. It should be in clear consice and formal tone of voice not over 1 page and/or 400 words.
5. Open with a hook for the recruiter: mentioning a big number, a big brand or a big achievement
6. Sound confident, positive and impactful by using an achievement oriented tone of voice and highlighting key skills that led me to achieving results
7. Make evident that there is a cultural fit by highlighting elements of how my profile aligns with the company vision and mission.
REQUIREMENTS:
Reiterate interest and call to action

COMPANY: {input_data.company}
COMPANY RESEARCH: {research}

JOB DESCRIPTION: {input_data.jd}

CANDIDATE BACKGROUND (from resume):
{json.dumps(input_data.resume_draft, indent=2)}



Return ONLY a JSON object:
{{
    "body": "The plain text cover letter body (3-4 paragraphs)",
    "info": {{
        "recipient": "Hiring Manager name or title",
        "street": "Company address if known",
        "city": "City",
        "state": "Province/State",
        "zip": "Postal Code"
    }}
}}

Keep it professional, specific, and concise. No markdown, no LaTeX formatting in the body text.
"""
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        content = response.content.replace("```json", "").replace("```", "").strip()
        res_data = json.loads(content)
    except Exception as e:
        res_data = {
            "body": f"I am writing to express my strong interest in the Data Engineering position at {input_data.company}. With over 2 years of experience building ETL pipelines and cloud data solutions, I am confident I can contribute effectively to your team.\\n\\nMy background includes extensive work with Azure Data Factory, Databricks, and Python, developing scalable data pipelines that support business intelligence and analytics. I have consistently delivered solutions that improve data quality and reduce processing time.\\n\\nI would welcome the opportunity to discuss how my skills align with your needs. Thank you for your consideration.",
            "info": {
                "recipient": "Hiring Manager",
                "street": "",
                "city": "Toronto",
                "state": "ON",
                "zip": "M5V 2L7"
            }
        }

    # Save files using helper function
    save_cover_letter_files(res_data['body'], input_data.company, input_data.resume_draft)
    
    # Compile
    subprocess.run(["pdflatex", "-interaction=nonstopmode", MAIN_TEX])
    if os.path.exists("main.pdf"): 
        os.replace("main.pdf", CL_PDF)
    
    return {"letter_text": res_data['body']}


@app.post("/save-cover-letter")
async def save_cl(data: SaveCLInput):
    """Save edited cover letter text and recompile without regenerating"""
    save_cover_letter_files(data.body, data.company, data.resume_draft)
    
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", MAIN_TEX],
        capture_output=True,
        text=True
    )
    
    if os.path.exists("main.pdf"):
        os.replace("main.pdf", CL_PDF)
    
    return {
        "status": "success" if result.returncode == 0 else "error",
        "message": "Cover letter updated and compiled"
    }


@app.post("/finalize-application")
async def finalize(data: FinalizeInput):
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_company = re.sub(r'\W+', '', data.company)
    safe_pos = re.sub(r'\W+', '', data.position)
    folder_name = f"{date_str}_{safe_pos}_{safe_company}"
    folder_path = os.path.join(ARCHIVE_DIR, folder_name)
    
    os.makedirs(folder_path, exist_ok=True)

    base_name = f"{date_str}_{safe_pos}_{safe_company}"
    jd_file = f"{base_name}_JD.txt"
    res_file = f"{base_name}_Resume.pdf"
    cl_file = f"{base_name}_coverletter.pdf"

    with open(os.path.join(folder_path, jd_file), "w") as f:
        f.write(data.jd)
    
    if os.path.exists(RESUME_PDF):
        shutil.copy(RESUME_PDF, os.path.join(folder_path, res_file))
    if os.path.exists(CL_PDF):
        shutil.copy(CL_PDF, os.path.join(folder_path, cl_file))

    apps = load_apps()
    apps.append({
        "date": date_str,
        "company": data.company,
        "position": data.position,
        "status": "Applied",
        "folder": folder_path,
        "jd_file": jd_file,
        "res_file": res_file,
        "cl_file": cl_file
    })

    with open(APPLICATIONS_FILE, "w") as f:
        json.dump(apps, f, indent=4)

    return {"status": "success"}

@app.get("/get-applications")
async def get_apps():
    return load_apps()

@app.post("/update-status")
async def update_status(data: StatusUpdate):
    apps = load_apps()
    if 0 <= data.index < len(apps):
        apps[data.index]["status"] = data.new_status
        with open(APPLICATIONS_FILE, "w") as f:
            json.dump(apps, f, indent=4)
        return {"status": "updated"}
    raise HTTPException(status_code=400, detail="Invalid index")