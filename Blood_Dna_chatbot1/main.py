import streamlit as st
from database.db import (
    init_db,
    save_medical_data,
    get_medical_data_by_id,
    get_chat_history  
)
from models.llm import analyze_medical_data
from process_image.image import preprocess_image, encode_image
from extract_pdf.pdf import encode_pdf
from utils.logger import setup_logger

# Initialize logger
logger = setup_logger('main')

# Initialize database at start
init_db()

st.title("🩺 Medical Data Processor")

# **Step 1: User ID Input**
st.subheader("Existing Patient Lookup")
user_id = st.text_input("Enter Patient ID (if existing)", key="user_id")

# **Step 2: New Patient Form (If No ID is Entered)**
st.subheader("New Patient Registration")
new_name = st.text_input("Patient Full Name", key="new_name")
new_age = st.number_input("Age", min_value=0, max_value=120, step=1)
new_weight = st.number_input("Weight (kg)", min_value=0.0, max_value=300.0, step=0.1)
new_height = st.number_input("Height (cm)", min_value=0.0, max_value=300.0, step=0.1)

if new_weight > 0 and new_height > 0:
    new_bmi = new_weight / ((new_height/100) ** 2)
    st.info(f"Patient BMI: {new_bmi:.1f}")

submitted_info = st.button("Save New Patient Information")

# **Step 3: Handle Existing Patient Lookup**
patient_data = None
if user_id:
    try:
        user_id = int(user_id)
        patient_data, patient_name = get_medical_data_by_id(user_id)

        if patient_data and patient_name:
            logger.info(f"Found records for Patient ID: {user_id} (Name: {patient_name})")
            st.session_state.processed_name = patient_name
            st.session_state.current_id = user_id  

            # **Display only records associated with this user ID**
            st.success(f"Patient Name: {patient_name}")
            
            if patient_data:
                st.write("### Previous Reports for this Patient:")
                for record in patient_data:
                    # Ensure the patient records are associated with this user ID
                    if record[0] == user_id:  
                        st.write(f"- {record[2]} (Type: {record[1]}, Uploaded: {record[-1]})")
            else:
                st.write("No previous reports found for this patient.")
            
            st.write("You can upload additional reports below.")
        else:
            logger.warning(f"No records found for ID: {user_id}")
            st.error("No existing records found. Please fill in new patient details.")

    except ValueError:
        st.error("Please enter a valid numeric ID")
        logger.warning("Invalid ID format entered")

# **Step 4: Save New Patient Info if No ID Provided**
elif submitted_info:
    if not new_name or new_age == 0 or new_weight == 0 or new_height == 0:
        logger.warning("Incomplete form submission")
        st.error("Please fill in all required patient fields")
        st.stop()

    st.session_state.processed_name = new_name
    st.session_state.personal_info = {
        "name": new_name,
        "age": new_age,
        "weight": new_weight,
        "height": new_height,
        "bmi": new_weight / ((new_height/100) ** 2)
    }
    st.success("New patient information saved! You can now upload reports.")

# **Step 5: File Upload Section (Only After ID Lookup or New Patient Registration)**
if 'processed_name' in st.session_state:
    with st.form("file_upload_form"):
        st.subheader("Upload Medical Reports")
        uploaded_files = st.file_uploader(
            "Upload Reports (JPG, PNG, PDF)", 
            type=["jpg", "png", "pdf"], 
            accept_multiple_files=True
        )
        submitted_files = st.form_submit_button("Analyze Reports")

        if submitted_files:
            if not uploaded_files:
                logger.warning("No files uploaded")
                st.error("Please upload at least one file")
                st.stop()
            
            with st.spinner("Processing medical data..."):
                processed_ids = []
                name = st.session_state.processed_name
                
                for file in uploaded_files:
                    logger.info(f"Processing file: {file.name}")
                    try:
                        report_type = None
                        
                        if file.type.startswith('image'):
                            img = preprocess_image(file)
                            if img:
                                base64_image = encode_image(img)
                                 
                                # Determine Report Type
                                initial_analysis = analyze_medical_data(
                                    messages=[{
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "Is this a DNA/genetic report or a blood test report?"},
                                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                                        ]
                                    }],
                                    is_vision=True
                                )
                                 
                                # Classify as Blood or DNA
                                report_type = "blood" if any(kw in initial_analysis.lower() 
                                                             for kw in ["cbc", "hemoglobin", "platelet"]) else "dna"
                                 
                                # Perform Detailed Analysis
                                analysis = analyze_medical_data(
                                    messages=[{
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "Analyze this medical report in detail"},
                                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                                        ]
                                    }],
                                    is_vision=True,
                                    data_type=report_type
                                )
                                 
                                file_id = save_medical_data(name, report_type, f"image_{file.name}", analysis)
                                processed_ids.append((file.name, file_id, report_type))
                                 
                        elif file.type == "application/pdf":
                            text = encode_pdf(file)
                            if text:
                                # Determine Report Type
                                report_type = "blood" if any(kw in text.lower() 
                                                             for kw in ["cbc", "hemoglobin", "platelet"]) else "dna"
                                 
                                # Perform Detailed Analysis
                                analysis = analyze_medical_data(
                                    messages=[{
                                        "role": "user",
                                        "content": f"Analyze this medical report in detail:\n{text}"
                                    }],
                                    is_vision=False,
                                    data_type=report_type
                                )
                                 
                                file_id = save_medical_data(name, report_type, text, analysis)
                                processed_ids.append((file.name, file_id, report_type))
                        
                        st.success(f"Processed {file.name} successfully as {report_type} report!")

                    except Exception as e:
                        logger.error(f"Error processing {file.name}: {str(e)}", exc_info=True)
                        st.error(f"Error processing {file.name}: {str(e)}")

                # Display processed files for the current user only
                st.write("### Processed Reports:")
                for filename, file_id, file_type in processed_ids:
                    st.write(f"- {filename} (ID: {file_id}, Type: {file_type})")

                logger.info("All files processed successfully")
                st.success("All reports uploaded and analyzed successfully!")

# **Step 6: Display Chatbot History for This User Only**
if 'current_id' in st.session_state:
    chat_history = get_chat_history(st.session_state.processed_name, "medical")
    st.subheader("Chatbot Medical History (Filtered for This Patient)")
    
    if chat_history:
        for chat in chat_history:
            st.write(f"**Q:** {chat['question']}")
            st.write(f"**A:** {chat['response']}")
            st.write("---")
    else:
        st.info("No chat history found for this patient.")
