# import streamlit as st
# import requests
# import os
# import base64
# import pandas as pd

# st.set_page_config(page_title="Resume Factory", layout="wide")

# # --- Session State Initialization ---
# if "resume_draft" not in st.session_state: st.session_state.resume_draft = None
# if "cl_text" not in st.session_state: st.session_state.cl_text = ""

# def display_pdf(file_path):
#     if os.path.exists(file_path):
#         with open(file_path, "rb") as f:
#             base64_pdf = base64.b64encode(f.read()).decode('utf-8')
#         return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850vh" type="application/pdf"></iframe>'
#     return "No PDF generated yet."

# # --- SIDEBAR NAVIGATION ---
# with st.sidebar:
#     st.title("🏗️ Resume Factory")
#     page = st.radio("Go to", ["Factory", "Applications"])
#     st.divider()

# # --- PAGE 1: FACTORY ---
# if page == "Factory":
#     st.header("Build New Application")
    
#     with st.sidebar:
#         company = st.text_input("Company Name")
#         position = st.text_input("Position Title")
#         jd = st.text_area("Job Description", height=200)
        
#         if st.button("🚀 Generate Resume", use_container_width=True):
#             res = requests.post("http://localhost:8000/generate-resume", json={"jd": jd})
#             st.session_state.resume_draft = res.json()
#             st.rerun()

#         if st.button("✍️ Generate Cover Letter", use_container_width=True):
#             if st.session_state.resume_draft:
#                 res = requests.post("http://localhost:8000/generate-cover-letter", json={
#                     "jd": jd, "resume_draft": st.session_state.resume_draft, "company": company
#                 })
#                 st.session_state.cl_text = res.json()["letter_text"]
#                 st.rerun()
        
#         st.divider()
#         if st.button("🛠️ Compile Everything", use_container_width=True):
#             requests.post("http://localhost:8000/save-resume", json={"draft": st.session_state.resume_draft})
#             requests.post("http://localhost:8000/compile-resume")
#             st.success("Compiled!")

#         if st.button("✅ Finalize & Archive", type="primary", use_container_width=True):
#             payload = {"company": company, "position": position, "jd": jd}
#             res = requests.post("http://localhost:8000/finalize-application", json=payload)
#             if res.status_code == 200:
#                 st.success("Application Archived Successfully!")

#     # Workspace
#     if st.session_state.resume_draft:
#         col_edit, col_prev = st.columns([1, 1])
#         with col_edit:
#             mode = st.radio("Editing Mode", ["Resume", "Cover Letter"], horizontal=True)
#             if mode == "Resume":
#                 st.session_state.resume_draft['summary'] = st.text_area("Summary", value=st.session_state.resume_draft.get('summary', ''), height=150)
#                 st.session_state.resume_draft['experience'] = st.text_area("Experience", value=st.session_state.resume_draft.get('experience', ''), height=400)
#                 st.session_state.resume_draft['skills'] = st.text_area("Skills", value=st.session_state.resume_draft.get('skills', ''), height=150)
#                 st.session_state.resume_draft['projects'] = st.text_area("Projects", value=st.session_state.resume_draft.get('projects', ''), height=300)
#             else:
#                 st.session_state.cl_text = st.text_area("Cover Letter Body", value=st.session_state.cl_text, height=600)

#         with col_prev:
#             target_pdf = "tailored_resume.pdf" if mode == "Resume" else "cover_letter.pdf"
#             st.subheader(f"Preview: {target_pdf}")
#             st.markdown(display_pdf(target_pdf), unsafe_allow_html=True)

# # --- PAGE 2: APPLICATIONS ---
# elif page == "Applications":
#     st.header("📂 Application Tracker")
    
#     apps_res = requests.get("http://localhost:8000/get-applications")
#     if apps_res.status_code == 200:
#         apps = apps_res.json()
        
#         if not apps:
#             st.info("No archived applications yet.")
#         else:
#             # 1. Summary Table
#             df = pd.DataFrame(apps)[["date", "company", "position", "status"]]
#             st.dataframe(df, use_container_width=True)

#             # 2. Selector & Status Updater
#             st.divider()
#             col_select, col_status = st.columns([2, 1])
            
#             with col_select:
#                 selection_idx = st.selectbox(
#                     "Select Application to View", 
#                     range(len(apps)), 
#                     format_func=lambda x: f"{apps[x]['company']} - {apps[x]['position']} ({apps[x]['date']})"
#                 )
#                 selected_app = apps[selection_idx]

#             with col_status:
#                 current_status = selected_app.get("status", "Applied")
#                 status_options = ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"]
#                 try:
#                     default_idx = status_options.index(current_status)
#                 except ValueError:
#                     default_idx = 0
                
#                 new_status = st.selectbox("Update Status", status_options, index=default_idx)
                
#                 if new_status != current_status:
#                     if st.button("Update Status"):
#                         update_res = requests.post("http://localhost:8000/update-status", 
#                                                 json={"index": selection_idx, "new_status": new_status})
#                         if update_res.status_code == 200:
#                             st.success(f"Status updated to {new_status}")
#                             st.rerun()

#             # 3. Split View Viewer
#             st.divider()
#             col_jd, col_doc = st.columns([1, 1])
            
#             with col_jd:
#                 st.subheader("Job Description")
#                 jd_path = os.path.join(selected_app['folder'], selected_app['jd_file'])
#                 if os.path.exists(jd_path):
#                     with open(jd_path, "r") as f:
#                         st.text_area("Original JD", value=f.read(), height=750, disabled=True)

#             with col_doc:
#                 doc_mode = st.radio("View", ["Resume", "Cover Letter"], horizontal=True)
#                 file_key = 'res_file' if doc_mode == "Resume" else 'cl_file'
#                 pdf_path = os.path.join(selected_app['folder'], selected_app[file_key])
#                 st.markdown(display_pdf(pdf_path), unsafe_allow_html=True)


# import streamlit as st
# import requests
# import os
# import base64
# import pandas as pd

# st.set_page_config(page_title="Resume Factory", layout="wide")

# # --- Session State ---
# if "resume_draft" not in st.session_state: st.session_state.resume_draft = None
# if "cl_text" not in st.session_state: st.session_state.cl_text = ""

# def display_pdf(file_path):
#     if os.path.exists(file_path):
#         with open(file_path, "rb") as f:
#             base64_pdf = base64.b64encode(f.read()).decode('utf-8')
#         return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850vh" type="application/pdf"></iframe>'
#     return "File not found."

# # --- NAVIGATION ---
# with st.sidebar:
#     st.title("🏗️ Resume Factory")
#     page = st.radio("Navigation", ["Factory", "Applications"])
#     st.divider()

# # --- PAGE: FACTORY ---
# if page == "Factory":
#     st.header("Build Application")
    
#     with st.sidebar:
#         company = st.text_input("Company Name")
#         position = st.text_input("Position Title")
#         jd = st.text_area("Job Description", height=200)
        
#         if st.button("🚀 Generate Resume", use_container_width=True):
#             try:
#                 res = requests.post("http://localhost:8000/generate-resume", json={"jd": jd})
#                 if res.status_code == 200:
#                     st.session_state.resume_draft = res.json()
#                     st.rerun()
#                 else:
#                     st.error("Failed to generate resume: " + res.text)
#             except Exception as e:
#                 st.error(f"Error generating resume: {str(e)}")

#         if st.button("✍️ Generate Cover Letter", use_container_width=True):
#             if st.session_state.resume_draft:
#                 try:
#                     res = requests.post("http://localhost:8000/generate-cover-letter", json={
#                         "jd": jd, "resume_draft": st.session_state.resume_draft, "company": company
#                     })
#                     if res.status_code == 200:
#                         st.session_state.cl_text = res.json()["letter_text"]
#                         st.rerun()
#                     else:
#                         st.error("Failed to generate cover letter: " + res.text)
#                 except Exception as e:
#                     st.error(f"Error generating cover letter: {str(e)}")

#         if st.button("🛠️ Compile & Refresh Preview", use_container_width=True, type="secondary"):
#             try:
#             # 1. Save current session state edits to the .tex file
#                 save_res = requests.post("http://localhost:8000/save-resume", json={"draft": st.session_state.resume_draft})
        
#             # 2. Compile the .tex into .pdf
#                 compile_res = requests.post("http://localhost:8000/compile-resume")
        
#                 if compile_res.status_code == 200:
#                     st.success("PDF Updated!")
#                     st.rerun() # Force streamlit to reload the PDF into the iframe
#                 else:
#                     st.error("Compilation failed.")
#             except Exception as e:
#                 st.error(f"Error: {str(e)}")   


#         if st.button("🛠️ Compile PDFs", use_container_width=True):
#             try:
#                 save_res = requests.post("http://localhost:8000/save-resume", json={"draft": st.session_state.resume_draft})
#                 compile_res = requests.post("http://localhost:8000/compile-resume")
#                 if compile_res.status_code == 200:
#                     compile_data = compile_res.json()
#                     if compile_data.get("status") == "success":
#                         st.success("PDFs Compiled!")
#                     else:
#                         st.error("Compilation failed: " + compile_data.get("log", ""))
#                 else:
#                     st.error("Failed to compile PDFs")
#             except Exception as e:
#                 st.error(f"Error compiling PDFs: {str(e)}")

#         if st.button("✅ Finalize & Archive", type="primary", use_container_width=True):
#             try:
#                 payload = {"company": company, "position": position, "jd": jd}
#                 res = requests.post("http://localhost:8000/finalize-application", json=payload)
#                 if res.status_code == 200:
#                     st.success("Archived!")
#                 else:
#                     st.error("Archive Failed: " + res.text)
#             except Exception as e:
#                 st.error(f"Error archiving: {str(e)}")

#     # Main Workspace
#     if st.session_state.resume_draft:
#         col_edit, col_prev = st.columns([1, 1])
#         with col_edit:
#             mode = st.radio("Editing Mode", ["Resume", "Cover Letter"], horizontal=True)
#             if mode == "Resume":
#                 st.session_state.resume_draft['summary'] = st.text_area("Summary", value=st.session_state.resume_draft.get('summary', ''), height=150)
#                 st.session_state.resume_draft['experience'] = st.text_area("Experience", value=st.session_state.resume_draft.get('experience', ''), height=400)
#                 st.session_state.resume_draft['skills'] = st.text_area("Skills", value=st.session_state.resume_draft.get('skills', ''), height=150)
#                 st.session_state.resume_draft['projects'] = st.text_area("Projects", value=st.session_state.resume_draft.get('projects', ''), height=200)   
#             else:
#                 st.session_state.cl_text = st.text_area("Cover Letter", value=st.session_state.cl_text, height=600)

#         with col_prev:
#             target_pdf = "tailored_resume.pdf" if mode == "Resume" else "cover_letter.pdf"
#             st.subheader(f"Preview: {target_pdf}")
#             st.markdown(display_pdf(target_pdf), unsafe_allow_html=True)

# # --- PAGE: APPLICATIONS ---
# elif page == "Applications":
#     st.header("📂 Application Tracker")
    
#     apps_res = requests.get("http://localhost:8000/get-applications")
#     if apps_res.status_code == 200:
#         apps = apps_res.json()
        
#         if not apps:
#             st.info("No applications archived yet.")
#         else:
#             # Table View
#             df = pd.DataFrame(apps)[["date", "company", "position", "status"]]
#             st.table(df)

#             # Detail Selector and Status Updater
#             st.divider()
#             col_sel, col_stat = st.columns([2, 1])
            
#             with col_sel:
#                 idx = st.selectbox("View Application", range(len(apps)), 
#                                   format_func=lambda x: f"{apps[x]['company']} | {apps[x]['position']}")
#                 selected = apps[idx]

#             with col_stat:
#                 st.write("") # Padding
#                 status_list = ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"]
#                 try: current_idx = status_list.index(selected["status"])
#                 except: current_idx = 0
                
#                 new_status = st.selectbox("Change Status", status_list, index=current_idx)
#                 if st.button("Update"):
#                     requests.post("http://localhost:8000/update-status", json={"index": idx, "new_status": new_status})
#                     st.rerun()

#             # Split View
#             st.divider()
#             v_col1, v_col2 = st.columns([1, 1])
#             with v_col1:
#                 st.subheader("Job Description")
#                 jd_path = os.path.join(selected['folder'], selected['jd_file'])
#                 if os.path.exists(jd_path):
#                     with open(jd_path, "r") as f:
#                         st.text_area("JD", value=f.read(), height=700, disabled=True)
            
#             with v_col2:
#                 doc_type = st.radio("Document", ["Resume", "Cover Letter"], horizontal=True)
#                 file_name = selected['res_file'] if doc_type == "Resume" else selected['cl_file']
#                 st.markdown(display_pdf(os.path.join(selected['folder'], file_name)), unsafe_allow_html=True)


# import streamlit as st
# import requests
# import os
# import base64
# import pandas as pd

# st.set_page_config(page_title="Resume Factory", layout="wide")

# # --- Session State ---
# if "resume_draft" not in st.session_state: 
#     st.session_state.resume_draft = None
# if "cl_text" not in st.session_state: 
#     st.session_state.cl_text = ""
# if "cl_info" not in st.session_state:
#     st.session_state.cl_info = {}
# if "generation_step" not in st.session_state:
#     st.session_state.generation_step = 0  # 0: start, 1: resume generated, 2: cover letter generated
# if "company" not in st.session_state:
#     st.session_state.company = ""
# if "position" not in st.session_state:
#     st.session_state.position = ""
# if "jd" not in st.session_state:
#     st.session_state.jd = ""

# def display_pdf(file_path):
#     if os.path.exists(file_path):
#         with open(file_path, "rb") as f:
#             base64_pdf = base64.b64encode(f.read()).decode('utf-8')
#         return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
#     return "<p style='color: gray; text-align: center; padding: 50px;'>No preview available yet. Generate and compile to see preview.</p>"

# # --- NAVIGATION ---
# with st.sidebar:
#     st.title("🏗️ Resume Factory")
#     page = st.radio("Navigation", ["🚀 Factory", "📂 Applications"])
#     st.divider()
    
#     if page == "🚀 Factory":
#         st.markdown("### Quick Guide")
#         st.markdown("""
#         1. Enter job details
#         2. Generate resume draft
#         3. Review & edit
#         4. Generate cover letter
#         5. Review & edit
#         6. Finalize & archive
#         """)

# # --- PAGE: FACTORY ---
# if page == "🚀 Factory":
#     st.header("🚀 Build Your Application")
    
#     # Step indicator
#     steps = ["📝 Job Details", "📄 Resume", "✉️ Cover Letter", "✅ Finalize"]
#     cols = st.columns(4)
#     for idx, (col, step) in enumerate(zip(cols, steps)):
#         with col:
#             if idx <= st.session_state.generation_step:
#                 st.success(step)
#             else:
#                 st.info(step)
    
#     st.divider()
    
#     # STEP 1: Job Details Input
#     st.subheader("Step 1: Job Details")
#     col1, col2 = st.columns(2)
#     with col1:
#         st.session_state.company = st.text_input("Company Name", value=st.session_state.company, placeholder="e.g., Google")
#     with col2:
#         st.session_state.position = st.text_input("Position Title", value=st.session_state.position, placeholder="e.g., Senior Data Engineer")
    
#     st.session_state.jd = st.text_area("Job Description", value=st.session_state.jd, height=200, placeholder="Paste the full job description here...")
    
#     # Generate Resume Button
#     col_btn1, col_btn2 = st.columns([1, 3])
#     with col_btn1:
#         generate_resume_btn = st.button("🚀 Generate Resume", use_container_width=True, type="primary", disabled=not st.session_state.jd)
#     with col_btn2:
#         if st.session_state.resume_draft:
#             st.success("✓ Resume draft generated")
    
#     if generate_resume_btn:
#         with st.spinner("🤖 AI is crafting your tailored resume..."):
#             try:
#                 res = requests.post("http://localhost:8000/generate-resume", json={"jd": st.session_state.jd})
#                 if res.status_code == 200:
#                     st.session_state.resume_draft = res.json()
#                     st.session_state.generation_step = max(st.session_state.generation_step, 1)
#                     st.success("✅ Resume generated! Review and edit below.")
#                     st.rerun()
#                 else:
#                     st.error("❌ Failed to generate resume: " + res.text)
#             except Exception as e:
#                 st.error(f"❌ Error: {str(e)}")
    
#     # STEP 2: Resume Editing
#     if st.session_state.resume_draft:
#         st.divider()
#         st.subheader("Step 2: Review & Edit Resume")
        
#         col_edit, col_preview = st.columns([1, 1])
        
#         with col_edit:
#             st.markdown("##### Edit Resume Sections")
            
#             with st.expander("📝 Summary", expanded=True):
#                 st.session_state.resume_draft['summary'] = st.text_area(
#                     "Professional Summary", 
#                     value=st.session_state.resume_draft.get('summary', ''), 
#                     height=120,
#                     key="summary_edit",
#                     help="Brief overview of your qualifications"
#                 )
            
#             with st.expander("💼 Experience", expanded=True):
#                 st.session_state.resume_draft['experience'] = st.text_area(
#                     "Work Experience", 
#                     value=st.session_state.resume_draft.get('experience', ''), 
#                     height=300,
#                     key="exp_edit",
#                     help="Your relevant work history"
#                 )
            
#             with st.expander("🛠️ Skills", expanded=False):
#                 st.session_state.resume_draft['skills'] = st.text_area(
#                     "Technical Skills", 
#                     value=st.session_state.resume_draft.get('skills', ''), 
#                     height=120,
#                     key="skills_edit",
#                     help="Your key technical competencies"
#                 )
            
#             with st.expander("🚀 Projects", expanded=False):
#                 st.session_state.resume_draft['projects'] = st.text_area(
#                     "Projects", 
#                     value=st.session_state.resume_draft.get('projects', ''), 
#                     height=200,
#                     key="projects_edit",
#                     help="Notable projects you've worked on"
#                 )
            
#             # Action buttons for resume
#             btn_col1, btn_col2, btn_col3 = st.columns(3)
#             with btn_col1:
#                 if st.button("🔄 Regenerate Resume", use_container_width=True):
#                     with st.spinner("Regenerating..."):
#                         try:
#                             res = requests.post("http://localhost:8000/generate-resume", json={"jd": st.session_state.jd})
#                             if res.status_code == 200:
#                                 st.session_state.resume_draft = res.json()
#                                 st.rerun()
#                         except Exception as e:
#                             st.error(f"Error: {str(e)}")
            
#             with btn_col2:
#                 if st.button("👁️ Update Preview", use_container_width=True, type="secondary"):
#                     with st.spinner("Compiling PDF..."):
#                         try:
#                             save_res = requests.post("http://localhost:8000/save-resume", json={"draft": st.session_state.resume_draft})
#                             compile_res = requests.post("http://localhost:8000/compile-resume")
#                             if compile_res.status_code == 200:
#                                 st.success("Preview updated!")
#                                 st.rerun()
#                             else:
#                                 st.error("Compilation failed")
#                         except Exception as e:
#                             st.error(f"Error: {str(e)}")
            
#             with btn_col3:
#                 if st.button("✅ Approve Resume", use_container_width=True, type="primary"):
#                     st.session_state.generation_step = max(st.session_state.generation_step, 2)
#                     st.rerun()
        
#         with col_preview:
#             st.markdown("##### PDF Preview")
#             st.markdown(display_pdf("tailored_resume.pdf"), unsafe_allow_html=True)
    
#     # STEP 3: Cover Letter Generation
#     if st.session_state.generation_step >= 2:
#         st.divider()
#         st.subheader("Step 3: Cover Letter")
        
#         col_btn1, col_btn2 = st.columns([1, 3])
#         with col_btn1:
#             generate_cl_btn = st.button("✉️ Generate Cover Letter", use_container_width=True, type="primary", disabled=not st.session_state.company)
#         with col_btn2:
#             if st.session_state.cl_text:
#                 st.success("✓ Cover letter generated")
        
#         if generate_cl_btn:
#             with st.spinner("🤖 AI is writing your cover letter..."):
#                 try:
#                     res = requests.post("http://localhost:8000/generate-cover-letter", json={
#                         "jd": st.session_state.jd, 
#                         "resume_draft": st.session_state.resume_draft, 
#                         "company": st.session_state.company
#                     })
#                     if res.status_code == 200:
#                         st.session_state.cl_text = res.json()["letter_text"]
#                         st.session_state.generation_step = max(st.session_state.generation_step, 3)
#                         st.success("✅ Cover letter generated!")
#                         st.rerun()
#                     else:
#                         st.error("❌ Failed to generate cover letter")
#                 except Exception as e:
#                     st.error(f"❌ Error: {str(e)}")
        
#         # Cover Letter Editing
#         if st.session_state.cl_text:
#             col_edit_cl, col_preview_cl = st.columns([1, 1])
            
#             with col_edit_cl:
#                 st.markdown("##### Edit Cover Letter")
#                 st.session_state.cl_text = st.text_area(
#                     "Cover Letter Body", 
#                     value=st.session_state.cl_text, 
#                     height=500,
#                     key="cl_edit",
#                     help="Edit your cover letter content"
#                 )
                
#                 btn_cl1, btn_cl2, btn_cl3 = st.columns(3)
#                 with btn_cl1:
#                     if st.button("🔄 Regenerate CL", use_container_width=True):
#                         with st.spinner("Regenerating..."):
#                             try:
#                                 res = requests.post("http://localhost:8000/generate-cover-letter", json={
#                                     "jd": st.session_state.jd, 
#                                     "resume_draft": st.session_state.resume_draft, 
#                                     "company": st.session_state.company
#                                 })
#                                 if res.status_code == 200:
#                                     st.session_state.cl_text = res.json()["letter_text"]
#                                     st.rerun()
#                             except Exception as e:
#                                 st.error(f"Error: {str(e)}")
                
#                 with btn_cl2:
#                     if st.button("👁️ Update CL Preview", use_container_width=True, type="secondary"):
#                         with st.spinner("Compiling PDF..."):
#                             try:
#                                 # Save and recompile cover letter
#                                 res = requests.post("http://localhost:8000/generate-cover-letter", json={
#                                     "jd": st.session_state.jd, 
#                                     "resume_draft": st.session_state.resume_draft, 
#                                     "company": st.session_state.company
#                                 })
#                                 st.success("Preview updated!")
#                                 st.rerun()
#                             except Exception as e:
#                                 st.error(f"Error: {str(e)}")
                
#                 with btn_cl3:
#                     if st.button("✅ Approve CL", use_container_width=True, type="primary"):
#                         st.success("Cover letter approved!")
            
#             with col_preview_cl:
#                 st.markdown("##### PDF Preview")
#                 st.markdown(display_pdf("cover_letter.pdf"), unsafe_allow_html=True)
    
#     # STEP 4: Finalize
#     if st.session_state.generation_step >= 3 and st.session_state.cl_text:
#         st.divider()
#         st.subheader("Step 4: Finalize & Archive")
        
#         st.info("📦 Ready to archive your application? This will save all documents to your application tracker.")
        
#         col1, col2, col3 = st.columns([1, 1, 2])
#         with col1:
#             if st.button("🗑️ Start Over", use_container_width=True):
#                 st.session_state.resume_draft = None
#                 st.session_state.cl_text = ""
#                 st.session_state.generation_step = 0
#                 st.rerun()
        
#         with col2:
#             if st.button("📥 Archive Application", use_container_width=True, type="primary"):
#                 with st.spinner("Archiving..."):
#                     try:
#                         payload = {
#                             "company": st.session_state.company, 
#                             "position": st.session_state.position, 
#                             "jd": st.session_state.jd
#                         }
#                         res = requests.post("http://localhost:8000/finalize-application", json=payload)
#                         if res.status_code == 200:
#                             st.success("✅ Application archived successfully!")
#                             st.balloons()
#                             # Reset for next application
#                             st.session_state.resume_draft = None
#                             st.session_state.cl_text = ""
#                             st.session_state.generation_step = 0
#                             st.session_state.company = ""
#                             st.session_state.position = ""
#                             st.session_state.jd = ""
#                         else:
#                             st.error("❌ Archive failed: " + res.text)
#                     except Exception as e:
#                         st.error(f"❌ Error: {str(e)}")

# # --- PAGE: APPLICATIONS ---
# elif page == "📂 Applications":
#     st.header("📂 Application Tracker")
    
#     try:
#         apps_res = requests.get("http://localhost:8000/get-applications")
#         if apps_res.status_code == 200:
#             apps = apps_res.json()
            
#             if not apps:
#                 st.info("📭 No applications archived yet. Head to the Factory to create your first one!")
#             else:
#                 # Summary Statistics
#                 col1, col2, col3, col4 = st.columns(4)
#                 with col1:
#                     st.metric("Total Applications", len(apps))
#                 with col2:
#                     st.metric("Applied", len([a for a in apps if a["status"] == "Applied"]))
#                 with col3:
#                     st.metric("Interviewing", len([a for a in apps if a["status"] == "Interviewing"]))
#                 with col4:
#                     st.metric("Offers", len([a for a in apps if a["status"] == "Offer"]))
                
#                 st.divider()
                
#                 # Table View with color coding
#                 df = pd.DataFrame(apps)[["date", "company", "position", "status"]]
                
#                 # Display styled table
#                 st.dataframe(
#                     df,
#                     use_container_width=True,
#                     hide_index=True,
#                     column_config={
#                         "date": "Date",
#                         "company": "Company",
#                         "position": "Position",
#                         "status": st.column_config.TextColumn("Status")
#                     }
#                 )
                
#                 # Detail Selector and Status Updater
#                 st.divider()
#                 st.subheader("📋 Application Details")
                
#                 col_sel, col_stat = st.columns([3, 1])
                
#                 with col_sel:
#                     idx = st.selectbox(
#                         "Select Application to View", 
#                         range(len(apps)), 
#                         format_func=lambda x: f"{apps[x]['date']} | {apps[x]['company']} - {apps[x]['position']}"
#                     )
#                     selected = apps[idx]
                
#                 with col_stat:
#                     status_list = ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"]
#                     status_colors = {
#                         "Applied": "🟦",
#                         "Interviewing": "🟨", 
#                         "Offer": "🟩",
#                         "Rejected": "🟥",
#                         "Ghosted": "⬜"
#                     }
                    
#                     try: 
#                         current_idx = status_list.index(selected["status"])
#                     except: 
#                         current_idx = 0
                    
#                     new_status = st.selectbox(
#                         "Update Status", 
#                         status_list, 
#                         index=current_idx,
#                         format_func=lambda x: f"{status_colors.get(x, '')} {x}"
#                     )
                    
#                     if new_status != selected["status"]:
#                         if st.button("💾 Save Status", use_container_width=True, type="primary"):
#                             try:
#                                 requests.post("http://localhost:8000/update-status", json={"index": idx, "new_status": new_status})
#                                 st.success(f"Status updated to {new_status}")
#                                 st.rerun()
#                             except Exception as e:
#                                 st.error(f"Error: {str(e)}")
                
#                 # Split View
#                 st.divider()
                
#                 # Document viewer tabs
#                 tab_jd, tab_resume, tab_cl = st.tabs(["📄 Job Description", "📝 Resume", "✉️ Cover Letter"])
                
#                 with tab_jd:
#                     jd_path = os.path.join(selected['folder'], selected['jd_file'])
#                     if os.path.exists(jd_path):
#                         with open(jd_path, "r") as f:
#                             jd_content = f.read()
#                         st.text_area("Job Description", value=jd_content, height=600, disabled=True)
#                     else:
#                         st.warning("Job description file not found")
                
#                 with tab_resume:
#                     res_path = os.path.join(selected['folder'], selected['res_file'])
#                     st.markdown(display_pdf(res_path), unsafe_allow_html=True)
                
#                 with tab_cl:
#                     cl_path = os.path.join(selected['folder'], selected['cl_file'])
#                     st.markdown(display_pdf(cl_path), unsafe_allow_html=True)
#         else:
#             st.error("Failed to load applications")
#     except Exception as e:
#         st.error(f"Error loading applications: {str(e)}")

import streamlit as st
import requests
import os
import base64
import pandas as pd

st.set_page_config(page_title="Resume Factory", layout="wide")

# --- Session State ---
if "resume_draft" not in st.session_state: 
    st.session_state.resume_draft = None
if "cl_text" not in st.session_state: 
    st.session_state.cl_text = ""
if "cl_info" not in st.session_state:
    st.session_state.cl_info = {}
if "generation_step" not in st.session_state:
    st.session_state.generation_step = 0  # 0: start, 1: resume generated, 2: cover letter generated
if "company" not in st.session_state:
    st.session_state.company = ""
if "position" not in st.session_state:
    st.session_state.position = ""
if "jd" not in st.session_state:
    st.session_state.jd = ""

def display_pdf(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
        except Exception as e:
            return f"<p style='color: red;'>Error loading PDF: {str(e)}</p>"
    return f"<p style='color: gray; text-align: center; padding: 50px;'>File not found: {file_path}<br>Generate and compile to see preview.</p>"

# --- NAVIGATION ---
with st.sidebar:
    st.title("🏗️ Resume Factory")
    page = st.radio("Navigation", ["🚀 Factory", "📂 Applications"])
    st.divider()
    
    if page == "🚀 Factory":
        st.markdown("### Quick Guide")
        st.markdown("""
        1. Enter job details
        2. Generate resume draft
        3. Review & edit
        4. Generate cover letter
        5. Review & edit
        6. Finalize & archive
        """)

# --- PAGE: FACTORY ---
if page == "🚀 Factory":
    st.header("🚀 Build Your Application")
    
    # Step indicator
    steps = ["📝 Job Details", "📄 Resume", "✉️ Cover Letter", "✅ Finalize"]
    cols = st.columns(4)
    for idx, (col, step) in enumerate(zip(cols, steps)):
        with col:
            if idx <= st.session_state.generation_step:
                st.success(step)
            else:
                st.info(step)
    
    st.divider()
    
    # STEP 1: Job Details Input
    st.subheader("Step 1: Job Details")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.company = st.text_input("Company Name", value=st.session_state.company, placeholder="e.g., Google")
    with col2:
        st.session_state.position = st.text_input("Position Title", value=st.session_state.position, placeholder="e.g., Senior Data Engineer")
    
    st.session_state.jd = st.text_area("Job Description", value=st.session_state.jd, height=200, placeholder="Paste the full job description here...")
    
    # Generate Resume Button
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        generate_resume_btn = st.button("🚀 Generate Resume", use_container_width=True, type="primary", disabled=not st.session_state.jd)
    with col_btn2:
        if st.session_state.resume_draft:
            st.success("✓ Resume draft generated")
    
    if generate_resume_btn:
        with st.spinner("🤖 AI is crafting your tailored resume..."):
            try:
                res = requests.post("http://localhost:8000/generate-resume", json={"jd": st.session_state.jd})
                if res.status_code == 200:
                    st.session_state.resume_draft = res.json()
                    st.session_state.generation_step = max(st.session_state.generation_step, 1)
                    
                    # Check if PDF was actually created
                    if os.path.exists("tailored_resume.pdf"):
                        st.success("✅ Resume generated and compiled!")
                    else:
                        st.warning("⚠️ Resume generated but PDF not found. Click 'Update Preview' to compile.")
                    st.rerun()
                else:
                    st.error("❌ Failed to generate resume: " + res.text)
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # STEP 2: Resume Editing
    if st.session_state.resume_draft:
        st.divider()
        st.subheader("Step 2: Review & Edit Resume")
        
        col_edit, col_preview = st.columns([1, 1])
        
        with col_edit:
            st.markdown("##### Edit Resume Sections")
            
            with st.expander("📝 Summary", expanded=True):
                st.session_state.resume_draft['summary'] = st.text_area(
                    "Professional Summary", 
                    value=st.session_state.resume_draft.get('summary', ''), 
                    height=120,
                    key="summary_edit",
                    help="Brief overview of your qualifications"
                )
            
            with st.expander("💼 Experience", expanded=True):
                st.session_state.resume_draft['experience'] = st.text_area(
                    "Work Experience", 
                    value=st.session_state.resume_draft.get('experience', ''), 
                    height=300,
                    key="exp_edit",
                    help="Your relevant work history"
                )
            
            with st.expander("🛠️ Skills", expanded=False):
                st.session_state.resume_draft['skills'] = st.text_area(
                    "Technical Skills", 
                    value=st.session_state.resume_draft.get('skills', ''), 
                    height=120,
                    key="skills_edit",
                    help="Your key technical competencies"
                )
            
            with st.expander("🚀 Projects", expanded=False):
                st.session_state.resume_draft['projects'] = st.text_area(
                    "Projects", 
                    value=st.session_state.resume_draft.get('projects', ''), 
                    height=200,
                    key="projects_edit",
                    help="Notable projects you've worked on"
                )
            
            # Action buttons for resume
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if st.button("🔄 Regenerate Resume", use_container_width=True):
                    with st.spinner("Regenerating..."):
                        try:
                            res = requests.post("http://localhost:8000/generate-resume", json={"jd": st.session_state.jd})
                            if res.status_code == 200:
                                st.session_state.resume_draft = res.json()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with btn_col2:
                if st.button("👁️ Update Preview", use_container_width=True, type="secondary"):
                    with st.spinner("Compiling PDF..."):
                        try:
                            save_res = requests.post("http://localhost:8000/save-resume", json={"draft": st.session_state.resume_draft})
                            compile_res = requests.post("http://localhost:8000/compile-resume")
                            if compile_res.status_code == 200:
                                st.success("Preview updated!")
                                st.rerun()
                            else:
                                st.error("Compilation failed")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with btn_col3:
                if st.button("✅ Approve Resume", use_container_width=True, type="primary"):
                    st.session_state.generation_step = max(st.session_state.generation_step, 2)
                    st.rerun()
        
        with col_preview:
            st.markdown("##### PDF Preview")
            # Debug info
            pdf_exists = os.path.exists("tailored_resume.pdf")
            if pdf_exists:
                file_size = os.path.getsize("tailored_resume.pdf")
                st.caption(f"✓ PDF found ({file_size} bytes)")
            else:
                st.caption("⚠ PDF not found - click 'Update Preview' to compile")
            
            st.markdown(display_pdf("tailored_resume.pdf"), unsafe_allow_html=True)
    
    # STEP 3: Cover Letter Generation
    if st.session_state.generation_step >= 2:
        st.divider()
        st.subheader("Step 3: Cover Letter")
        
        col_btn1, col_btn2 = st.columns([1, 3])
        with col_btn1:
            generate_cl_btn = st.button("✉️ Generate Cover Letter", use_container_width=True, type="primary", disabled=not st.session_state.company)
        with col_btn2:
            if st.session_state.cl_text:
                st.success("✓ Cover letter generated")
        
        if generate_cl_btn:
            with st.spinner("🤖 AI is writing your cover letter..."):
                try:
                    res = requests.post("http://localhost:8000/generate-cover-letter", json={
                        "jd": st.session_state.jd, 
                        "resume_draft": st.session_state.resume_draft, 
                        "company": st.session_state.company
                    })
                    if res.status_code == 200:
                        st.session_state.cl_text = res.json()["letter_text"]
                        st.session_state.generation_step = max(st.session_state.generation_step, 3)
                        st.success("✅ Cover letter generated!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to generate cover letter")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # Cover Letter Editing
        if st.session_state.cl_text:
            col_edit_cl, col_preview_cl = st.columns([1, 1])
            
            with col_edit_cl:
                st.markdown("##### Edit Cover Letter")
                st.session_state.cl_text = st.text_area(
                    "Cover Letter Body", 
                    value=st.session_state.cl_text, 
                    height=500,
                    key="cl_edit",
                    help="Edit your cover letter content"
                )
                
                btn_cl1, btn_cl2, btn_cl3 = st.columns(3)
                with btn_cl1:
                    if st.button("🔄 Regenerate CL", use_container_width=True):
                        with st.spinner("Regenerating..."):
                            try:
                                res = requests.post("http://localhost:8000/generate-cover-letter", json={
                                    "jd": st.session_state.jd, 
                                    "resume_draft": st.session_state.resume_draft, 
                                    "company": st.session_state.company
                                })
                                if res.status_code == 200:
                                    st.session_state.cl_text = res.json()["letter_text"]
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                with btn_cl2:
                    if st.button("👁️ Update CL Preview", use_container_width=True, type="secondary"):
                        with st.spinner("Compiling PDF..."):
                            try:
                                # Save edited cover letter and recompile (without regenerating)
                                res = requests.post("http://localhost:8000/save-cover-letter", json={
                                    "body": st.session_state.cl_text,
                                    "company": st.session_state.company,
                                    "resume_draft": st.session_state.resume_draft
                                })
                                if res.status_code == 200:
                                    st.success("Preview updated!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update preview")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                with btn_cl3:
                    if st.button("✅ Approve CL", use_container_width=True, type="primary"):
                        st.success("Cover letter approved!")
            
            with col_preview_cl:
                st.markdown("##### PDF Preview")
                st.markdown(display_pdf("cover_letter.pdf"), unsafe_allow_html=True)
    
    # STEP 4: Finalize
    if st.session_state.generation_step >= 3 and st.session_state.cl_text:
        st.divider()
        st.subheader("Step 4: Finalize & Archive")
        
        st.info("📦 Ready to archive your application? This will save all documents to your application tracker.")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Start Over", use_container_width=True):
                st.session_state.resume_draft = None
                st.session_state.cl_text = ""
                st.session_state.generation_step = 0
                st.rerun()
        
        with col2:
            if st.button("📥 Archive Application", use_container_width=True, type="primary"):
                with st.spinner("Archiving..."):
                    try:
                        payload = {
                            "company": st.session_state.company, 
                            "position": st.session_state.position, 
                            "jd": st.session_state.jd
                        }
                        res = requests.post("http://localhost:8000/finalize-application", json=payload)
                        if res.status_code == 200:
                            st.success("✅ Application archived successfully!")
                            st.balloons()
                            # Reset for next application
                            st.session_state.resume_draft = None
                            st.session_state.cl_text = ""
                            st.session_state.generation_step = 0
                            st.session_state.company = ""
                            st.session_state.position = ""
                            st.session_state.jd = ""
                        else:
                            st.error("❌ Archive failed: " + res.text)
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

# --- PAGE: APPLICATIONS ---
elif page == "📂 Applications":
    st.header("📂 Application Tracker")
    
    try:
        apps_res = requests.get("http://localhost:8000/get-applications")
        if apps_res.status_code == 200:
            apps = apps_res.json()
            
            if not apps:
                st.info("📭 No applications archived yet. Head to the Factory to create your first one!")
            else:
                # Summary Statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Applications", len(apps))
                with col2:
                    st.metric("Applied", len([a for a in apps if a["status"] == "Applied"]))
                with col3:
                    st.metric("Interviewing", len([a for a in apps if a["status"] == "Interviewing"]))
                with col4:
                    st.metric("Offers", len([a for a in apps if a["status"] == "Offer"]))
                
                st.divider()
                
                # Table View with color coding
                df = pd.DataFrame(apps)[["date", "company", "position", "status"]]
                
                # Display styled table
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date": "Date",
                        "company": "Company",
                        "position": "Position",
                        "status": st.column_config.TextColumn("Status")
                    }
                )
                
                # Detail Selector and Status Updater
                st.divider()
                st.subheader("📋 Application Details")
                
                col_sel, col_stat = st.columns([3, 1])
                
                with col_sel:
                    idx = st.selectbox(
                        "Select Application to View", 
                        range(len(apps)), 
                        format_func=lambda x: f"{apps[x]['date']} | {apps[x]['company']} - {apps[x]['position']}"
                    )
                    selected = apps[idx]
                
                with col_stat:
                    status_list = ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"]
                    status_colors = {
                        "Applied": "🟦",
                        "Interviewing": "🟨", 
                        "Offer": "🟩",
                        "Rejected": "🟥",
                        "Ghosted": "⬜"
                    }
                    
                    try: 
                        current_idx = status_list.index(selected["status"])
                    except: 
                        current_idx = 0
                    
                    new_status = st.selectbox(
                        "Update Status", 
                        status_list, 
                        index=current_idx,
                        format_func=lambda x: f"{status_colors.get(x, '')} {x}"
                    )
                    
                    if new_status != selected["status"]:
                        if st.button("💾 Save Status", use_container_width=True, type="primary"):
                            try:
                                requests.post("http://localhost:8000/update-status", json={"index": idx, "new_status": new_status})
                                st.success(f"Status updated to {new_status}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                # Split View
                st.divider()
                
                # Document viewer tabs
                tab_jd, tab_resume, tab_cl = st.tabs(["📄 Job Description", "📝 Resume", "✉️ Cover Letter"])
                
                with tab_jd:
                    jd_path = os.path.join(selected['folder'], selected['jd_file'])
                    if os.path.exists(jd_path):
                        with open(jd_path, "r") as f:
                            jd_content = f.read()
                        st.text_area("Job Description", value=jd_content, height=600, disabled=True)
                    else:
                        st.warning("Job description file not found")
                
                with tab_resume:
                    res_path = os.path.join(selected['folder'], selected['res_file'])
                    st.markdown(display_pdf(res_path), unsafe_allow_html=True)
                
                with tab_cl:
                    cl_path = os.path.join(selected['folder'], selected['cl_file'])
                    st.markdown(display_pdf(cl_path), unsafe_allow_html=True)
        else:
            st.error("Failed to load applications")
    except Exception as e:
        st.error(f"Error loading applications: {str(e)}")