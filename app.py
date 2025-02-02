from flask import Flask, render_template, request, redirect, url_for
import os
import json
import pandas as pd
import base64
from openai import OpenAI

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Use the OPENAI_API_KEY environment variable
api_key = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI client
client = OpenAI(api_key=api_key)


# Token counting function

def count_tokens(text):
    return len(text.split())


# Parsing and truncation logic



def parse_patient(patient):
    return {
        "id": patient.get("id"),
        "name": " ".join(patient.get("name", [{}])[0].get("given", []) + [patient.get("name", [{}])[0].get("family", "")]),
        "gender": patient.get("gender"),
        "birthDate": patient.get("birthDate"),
        "address": patient.get("address", [{}])[0].get("text"),
        #"Time": patient.get("meta", {}).get("lastUpdated", "No time available")
    }

def parse_diagnosticreport(report):
    encoded_data = report.get("presentedForm", [{}])[0].get("data", "")
    try:
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        decoded_data = "No meaningful data available"

    return {
        "tests": ", ".join([result.get("display", "") for result in report.get("result", []) if result.get("display")]),
        "data": decoded_data if len(decoded_data) > 0 and decoded_data != "0" else "No relevant information provided.",
        "Time": report.get("effectiveDateTime", "No time available")
    }

def parse_care_plan(care_plan):
    return {
        "category": ", ".join([c.get("coding", [{}])[0].get("display", "") for c in care_plan.get("category", [])]),
        #"description": care_plan.get("description", "No description available"),
        "status": care_plan.get("status", "No status available"),
        "created": care_plan.get("created", "No creation date available"),
        "activities": ", ".join([a.get("detail", {}).get("code", {}).get("coding", [{}])[0].get("display", "") for a in care_plan.get("activity", [])])
    }
def parse_condition(condition):
    return {
        "diagnosis": condition.get("code", {}).get("coding", [{}])[0].get("display"),
        "category": ", ".join([c.get("coding", [{}])[0].get("display", "") for c in condition.get("category", [])]),
        #"Time": condition.get("recordedDate", "No time available")
        "Time": condition.get("meta", {}).get("lastUpdated", "No time available")
    }







def generate_summaries_with_openai(insights):
    summaries = []
    for insight in insights:
        try:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this medical insight for a layperson: {insight}"
                    }
                ],
                model="gpt-4o"
            )
            summaries.append(response.choices[0].message.content.strip())
        except Exception as e:
            summaries.append(f"Error in generating summary: {e}")
    return summaries


def generate_insights_with_openai(patient, care_plans, diagnostic_reports, conditions):
    prompt = f"""
    Patient Information:
    Name: {patient['name']}
    Gender: {patient['gender']}
    Birth Date: {patient['birthDate']}
    Address: {patient['address']}

    Conditions:
    {', '.join([f"Diagnosis: {cp['diagnosis']}, Category: {cp['category']}, Time: {cp['Time']}" for cp in conditions])}

    Care Plans:
    {', '.join([f"Category: {cp['category']}, Activities: {cp['activities']}, Created: {cp['created']}" for cp in care_plans])}

    Diagnostic Reports:
    {', '.join([f"Tests: {dr['tests']}, Data: {dr['data']}, Time: {dr['Time']}" for dr in diagnostic_reports])}

    Generate detailed health insights and observations for this patient.
    Ps:Don't say we don't know or there is lack of information or results is unknown. give result based on what we know.
    """
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="gpt-4"
        )
        return [response.choices[0].message.content.strip()]
    except Exception as e:
        return [f"Error in generating insights: {e}"]


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        with open(filepath, 'r') as f:
            data = json.load(f)

        patient_data = None
        diagnostic_reports = []
        care_plans = []
        conditions = []
        for entry in data:
            resource_type = entry.get("resourceType")
            if resource_type == "Patient":
                patient_data = parse_patient(entry)
            elif resource_type == "DiagnosticReport":
                diagnostic_reports.append(parse_diagnosticreport(entry))
            elif resource_type == "CarePlan":
                care_plans.append(parse_care_plan(entry))
            elif resource_type == "Condition":
                conditions.append(parse_condition(entry))

        if not patient_data:
            return "No patient data found in the JSON."

        insights = generate_insights_with_openai(patient_data, care_plans, diagnostic_reports,conditions)
        summaries = generate_summaries_with_openai(insights)

        return render_template('results.html', insights=insights, summaries=summaries)

    return redirect(url_for('index'))


@app.route('/medical_history')
def medical_history():
    return render_template('medical_history.html')


@app.route('/personal_info')
def personal_info():
    return render_template('personal_info.html')


@app.route('/appointments')
def appointments():
    return render_template('appointments.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


if __name__ == '__main__':
    app.run(debug=True)
