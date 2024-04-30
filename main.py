# Install Dependencies
import os
import time
import streamlit as st
from st_copy_to_clipboard import st_copy_to_clipboard
import pandas as pd
import openai
from PIL import Image
import pytesseract
import PyPDF2

# Load ML Pkgs
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier

# Transformers
from sklearn.feature_extraction.text import CountVectorizer

# Others
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# Load Pkgs
from sklearn.multioutput import MultiOutputClassifier

# Load file upload folder (for screenshots)
upload_dir = "file_upload" # Replace accordingly
output_dir = "file_output" # Replace accordingly
output_file = "file_output/final_output.txt" # Replace accordingly
os.makedirs(upload_dir, exist_ok=True)

# Load Dataset
df = pd.read_csv("dependencies/CA_data.csv", encoding='latin1')
df = df.dropna()
df = df.rename(columns=lambda x: x.strip())

# Features & Labels
Xfeatures = df['Ticket subject']
ylabels = df[['Ticket Type', 'Ticket priority', 'Module', 'Product']]

# Split Data
x_train,x_test,y_train,y_test = train_test_split(Xfeatures,ylabels,test_size=0.5,random_state=7)

# Build a pieline for the model
pipe_lr = Pipeline(steps=[('cv',CountVectorizer()),
                        ('lr_multi',MultiOutputClassifier(LogisticRegression()))])

# Load Dataset labels
type = df['Ticket Type'].unique()
priority = df['Ticket priority'].unique()
module = df['Module'].unique()
product = df['Product'].unique()

# Azure OpenAI Key
openai.api_type = "azure"
openai.api_version = "2024-02-01" 
openai.api_base = os.environ.get("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.environ.get("AZURE_OPENAI_KEY")

# Define the Streamlit app layout
def main():
    st.title('Customer Advocacy SmartTickets')

    # Form input
    with st.form(key='my_form'):
        st.header('Submit a Ticket')
        st.markdown("<hr>", unsafe_allow_html=True)

        # Text input
        # File uploads
        subject_type = st.text_input('Subject Type', max_chars=100)
        ticket_body = st.text_area('Ticket Body', height=150)   
        uploaded_files = st.file_uploader('Upload Screenshots', type=["jpg", "pdf", "png", "jpeg"], accept_multiple_files=True)
        
        # Upload file button (not a requirement)
        upload_file_button = st.form_submit_button(label='Upload Files')

        # Upload the files selected
        if upload_file_button:
            # Delete uploaded files
            files = os.listdir(upload_dir)
            for file in files:
                    os.remove(os.path.join(upload_dir, file))

            # Delete output files
            outputs = os.listdir(output_dir)
            for output in outputs:
                os.remove(os.path.join(output_dir, output))

            # Upload completion
            if not uploaded_files:
                st.warning("No files were selected. Please select at least one file.")
            else:
                with st.spinner('Uploading Files...'):
                    for uploaded_file in uploaded_files:
                        with open(os.path.join(upload_dir, uploaded_file.name), "wb") as f:
                            f.write(uploaded_file.read())

                    # Process each uploaded image or PDF file
                    for i, uploaded_file in enumerate(uploaded_files, start=1):
                        for filename in os.listdir(upload_dir):
                            if filename.endswith('.jpg') or filename.endswith('.jpeg'):
                                
                                # Extract text from image
                                with Image.open(uploaded_file) as img:
                                    text = pytesseract.image_to_string(img)
                                
                                # Save extracted text
                                with open(f'file_output/upload_text_{i}.txt', 'w') as file:
                                    file.write(text)

                            elif filename.endswith('.pdf'):
                                pdf_file = open(uploaded_file, 'rb')
                                pdf_reader = PyPDF2.PdfReader(pdf_file)

                                # Save extracted text
                                with open(f'file_output/upload_text_{i}.txt', 'w') as file:
                                    for page_num in range(len(pdf_reader.pages)):
                                        page = pdf_reader.pages[page_num]
                                        file.write(page.extract_text())
                    time.sleep(5)
                st.success(f"All files have been uploaded successfully.")

        # Please each .txt (context) into one main .txt file
        with open(output_file, 'a') as output:
            for filename in os.listdir(output_dir):
                if filename.endswith('.txt'):
                    with open(os.path.join(output_dir, filename), 'r') as file:
                        file_contents = file.read()
                output.write(file_contents + '\n---\n')
        with open(output_file, 'r') as context:
            global screenshot_text
            screenshot_text = context.read()

        st.markdown("<hr>", unsafe_allow_html=True)

        # Initializing text classification
        submit_button = st.form_submit_button(label='Generate Tags')

        # Concatenate final string
        input_text = subject_type + "; " + ticket_body

        # Form submission
        if submit_button and (not subject_type or not ticket_body):
            st.warning('Please fill in both Subject Type and Ticket Body.')
        elif submit_button and (subject_type and ticket_body):
            with st.spinner('Loading Ticket Tags...'):
                # Fit on Dataset
                pipe_lr.fit(x_train,y_train)

                # Accuracy Score
                pipe_lr.score(x_test,y_test)

                # ML estimators for multi-output classification
                pipe = Pipeline(steps=[('cv',CountVectorizer()),('rf',KNeighborsClassifier(n_neighbors=4))])
                pipe.fit(x_train,y_train)

                # Results
                arr = pipe.predict([input_text])
                global value_1, value_2, value_3, value_4
                value_1 = arr[0][0]
                value_2 = arr[0][1]
                value_3 = arr[0][2]
                value_4 = arr[0][3]

                # Create an empty list for accuracy
                rationale_list = []

                rat_prompt_1 = f"""
                Now, based on the criteria presented below, explain the reason for 
                such given category tag: '''{value_1}'''. The context for your explanation
                will come from '''{input_text}'''. Please make it direct and concise for the
                reader to quickly understand the context and reasons.
                """

                rat_output_1 = openai.ChatCompletion.create(
                    engine=os.environ.get("LLM_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
                        {"role": "user", "content": rat_prompt_1}
                    ]
                )
                rat_output_1 = rat_output_1['choices'][0]['message']['content']
                rationale_list.append(rat_output_1)

                rat_prompt_2 = f"""
                Now, based on the criteria presented below, explain the reason for 
                such given category tag: '''{value_2}'''. The context for your explanation
                will come from '''{input_text}'''. Please make it direct and concise for the
                reader to quickly understand the context and reasons.
                """

                rat_output_2 = openai.ChatCompletion.create(
                    engine=os.environ.get("LLM_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
                        {"role": "user", "content": rat_prompt_2}
                    ]
                )
                rat_output_2 = rat_output_2['choices'][0]['message']['content']
                rationale_list.append(rat_output_2)

                rat_prompt_3 = f"""
                Now, based on the criteria presented below, explain the reason for 
                such given category tag: '''{value_3}'''. The context for your explanation
                will come from '''{input_text}'''. Please make it direct and concise for the
                reader to quickly understand the context and reasons.
                """

                rat_output_3 = openai.ChatCompletion.create(
                    engine=os.environ.get("LLM_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
                        {"role": "user", "content": rat_prompt_3}
                    ]
                )
                rat_output_3 = rat_output_3['choices'][0]['message']['content']
                rationale_list.append(rat_output_3)

                rat_prompt_4 = f"""
                Now, based on the criteria presented below, explain the reason for 
                such given category tag: '''{value_4}'''. The context for your explanation
                will come from '''{input_text}'''. Please make it direct and concise for the
                reader to quickly understand the context and reasons.
                """

                rat_output_4 = openai.ChatCompletion.create(
                    engine=os.environ.get("LLM_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
                        {"role": "user", "content": rat_prompt_4}
                    ]
                )
                rat_output_4 = rat_output_4['choices'][0]['message']['content']
                rationale_list.append(rat_output_4)

                # Trim whitespace from each element in the list
                final_rationale = [item.strip() for item in rationale_list]
                
                global rationale_1, rationale_2, rationale_3, rationale_4
                rationale_1 = final_rationale[0]
                rationale_2 = final_rationale[1]
                rationale_3 = final_rationale[2]
                rationale_4 = final_rationale[3]
                time.sleep(5)

            # Display table
            st.header('Ticket Labels')

            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("Ticket Type")
                st.code(value_1, language="python")
                st.markdown(rationale_1)

            with col2:
                st.markdown("Module")
                st.code(value_3, language="python")
                st.markdown(rationale_3)

            col3, col4 = st.columns(2)

            with col3:
                st.markdown("Ticket Priority")
                st.code(value_2, language="python")
                st.markdown(rationale_2)

            with col4:
                st.markdown("Product")
                st.code(value_4, language="python")
                st.markdown(rationale_4)

            # Space below the tables
            st.markdown("""
            """)

# Run the Streamlit app
if __name__ == '__main__':
    main()