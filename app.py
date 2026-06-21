import base64
import os
# from PIL import Image
from openai import OpenAI
# import pytesseract
import io
import json
# import pymupdf
# import requests
import pandas as pd

# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# get columns to be extracted

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def _response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body) if not isinstance(body, str) else body,
    }


def _is_options(event):
    # API Gateway REST API v1
    if event.get('httpMethod') == 'OPTIONS':
        return True
    # API Gateway HTTP API v2 / Lambda Function URL
    try:
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return True
    except (AttributeError, TypeError):
        pass
    return False


def lambda_handler(event, context):
    try:
        print("Received raw event:", json.dumps(event))

        if _is_options(event):
            return _response(200, '')

        # API Gateway wraps payload in body as a string
        if 'body' in event and event['body']:
            try:
                body = json.loads(event['body'])
            except:
                body = event
        else:
            body = event

        columns = body.get("columns")
        as_json = body.get("as_json")
        content = body.get("text")
        # columns_list = [col for col in columns if isinstance(col, str) and col.strip()];
        
        # return _response(200, {'message': "Successfully converted", 'json_content': ", ".join(columns_list)})
        if not columns or not content:
            return _response(400, {'error': f'No column or No content provided. {columns} Use "text" (string).'})
        # Accept a single URL string or an array of URLs
        if isinstance(columns, list):
            columns_list = [col for col in columns if isinstance(col, str) and col.strip()];
        else:
            return _response(400, {'error': f'Invalid column type, expect a string'})
        try:
            # text = ocr_convert(paths=image_urls, page=[0])
            text = content
            print("column list")
            print(", ".join(columns_list));
            ai_response: list[object] = get_prompt(invoice_text=text,  column=", ".join(columns_list));
            print("as json")
            print(as_json)
            if as_json:
                print("as json here")
                print(ai_response);
                return _response(200, {'message': "Successfully converted", 'json_content': ai_response})
            else:
                get_file = convert_to_excel(column=columns_list, data=ai_response);
                return _response(200, {'message': "Successfully converted", 'json_content': get_file})
        
        except Exception as e:
            print(f"OCR failed: {e}")
            return _response(500, {'error': str(e)})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return _response(500, {'error': str(e)})


def get_prompt(invoice_text: str, column: str):
    print("AI column")
    print(column);
    client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url="https://api.deepseek.com")

    system_prompt = """
        You are an invoice data extraction assistant. Your job is to extract user-specified fields from one or more invoices or credit notes and return them as a JSON array, where each object represents a single invoice.

        The user will provide a list of column names to extract. You must:
        1. Use EXACTLY the column names the user provides as the JSON keys.
        2. Extract the corresponding value for each column from the invoice text.
        3. Each object in the array represents one invoice or credit note.

        Rules:
        1. Return ONLY a valid JSON array — no markdown, no explanation, no preamble.
        2. Even if only one invoice is provided, always return a JSON array with one object.
        3. If a field cannot be found in a given invoice, set its value to null.
        4. Clean up amounts: strip currency symbols and return them as numbers (e.g. 1241.45 not "£1,241.45").
        5. Dates should be returned in ISO 8601 format (YYYY-MM-DD) where possible.
        6. For address fields, return as a single string with commas separating each line.
        7. Never guess or infer values that aren't explicitly in the text.
        8. Only extract the columns the user specifies — do not add extra fields.

        Example:

        User provides columns: for example: ["supplier_name", "total_amount", "invoice_date", "account_number"]
        ONLY extract the COLUMN(S) specify by the USER

        Expected output:
        [
        {
            "supplier_name": "ENGIE Power Limited",
            "total_amount": 1241.45,
            "invoice_date": "2025-06-25",
            "account_number": "11633129"
        },
        {
            "supplier_name": "British Gas",
            "total_amount": 340.00,
            "invoice_date": "2025-05-10",
            "account_number": "98271623"
        }
        ]
    """

    user_prompt = f"""
    Extract the following columns from the invoice below:
    {column}

    Invoice text:
    {invoice_text}
    """
    
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2000,
        stream=False,
        response_format={'type': 'json_object'},
    )
    print("AI response");
    print(response.choices[0]);
    if response.choices[0].message.content:
        return json.loads(response.choices[0].message.content)
    return [];


def convert_to_excel(data: list[object], column: list[str]):
    buffer = io.BytesIO()
    dataFrame = pd.DataFrame(columns=column, data=data)
    dataFrame.to_excel(buffer, index=False)
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8"),