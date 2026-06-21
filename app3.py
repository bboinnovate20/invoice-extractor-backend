# import base64

# from PIL import Image
# from openai import OpenAI
# import pytesseract
# import io
# import json
# import pymupdf
# import requests
# import pandas as pd

# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# # get columns to be extracted

# CORS_HEADERS = {
#     'Access-Control-Allow-Origin': '*',
#     'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
#     "Access-Control-Allow-Headers": "Content-Type,Authorization",
# }


# def _response(status_code, body):
#     return {
#         'statusCode': status_code,
#         'headers': CORS_HEADERS,
#         'body': json.dumps(body) if not isinstance(body, str) else body,
#     }


# def _is_options(event):
#     # API Gateway REST API v1
#     if event.get('httpMethod') == 'OPTIONS':
#         return True
#     # API Gateway HTTP API v2 / Lambda Function URL
#     try:
#         if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
#             return True
#     except (AttributeError, TypeError):
#         pass
#     return False


# def lambda_handler(event, context):
#     try:
#         print("Received raw eventsssss:", json.dumps(event))

#         if _is_options(event):
#             return _response(200, '')

#         raw = event.get('image_urls')
#         columns = event.get("columns")
#         as_json = event.get("as_json")
        
#         if not columns or not raw:
#             return _response(400, {'error': 'No column or No image URL(s) provided. Use "image" (string or array).'})
#         # Accept a single URL string or an array of URLs
#         if isinstance(columns, list):
#             columns_list = [col for col in columns if isinstance(col, str) and col.strip()];
#         else:
#             return _response(400, {'error': f'Invalid column type, expect a string'})
#         if isinstance(raw, str):
#             image_urls = [raw]
#         elif isinstance(raw, list):
#             image_urls = [u for u in raw if isinstance(u, str) and u.strip()]
#         else:
#             return _response(400, {'error': f'Invalid type for "image": expected string or array, got {type(raw).__name__}'})
        
#         if not image_urls:
#             return _response(400, {'error': 'No valid image URLs provided.'})

#         try:
#             text = ocr_convert(paths=image_urls, page=[0])

#             ai_response: list[object] = get_prompt(", ".join(columns_list), text);
#             if as_json:
#                 print(ai_response);
#                 return _response(200, {'message': "Successfully converted", 'json_content': ai_response})
#             else:
#                 get_file = convert_to_excel(column=columns_list, data=ai_response);
#                 return _response(200, {'message': "Successfully converted", 'json_content': get_file})
        
#         except Exception as e:
#             print(f"OCR failed: {e}")
#             return _response(500, {'error': str(e)})

#     except Exception as e:
#         print(f"Unhandled error: {e}")
#         return _response(500, {'error': str(e)})


# def pdf_to_images(path: str, pages: list[int]) -> list[Image.Image]:
#     # --- FIX 3: Validate URL here too as a safety net ---
#     if not path or not path.startswith('http'):
#         raise ValueError(f"Invalid URL passed to pdf_to_images: {path!r}")

#     r = requests.get(path, timeout=30)
#     r.raise_for_status()  # Raises an error for 4xx/5xx responses

#     doc = pymupdf.Document(stream=r.content)
#     total_pages = len(doc)

#     if pages is None:
#         pages = list(range(total_pages))
#     else:
#         pages = [p for p in pages if 0 <= p < total_pages]

#     pil_images: list[Image.Image] = []
#     for page_number in pages:
#         current_page = doc[page_number]
#         pixmap = current_page.get_pixmap(dpi=300)
#         image = Image.open(io.BytesIO(pixmap.tobytes("png")))
#         pil_images.append(image)

#     doc.close()
#     return pil_images


# # --- FIX 4: Renamed param from 'path' to 'paths' to be clear it's a list ---
# def ocr_convert(paths: list[str], page: list[int]) -> str:
#     text = ""
#     max_chunk = 3
#     chunks = [paths[i:i + max_chunk] for i in range(0, len(paths), max_chunk)]
#     number_chunk = 0

#     for chunk_idx, chunk in enumerate(chunks):
#         for k, each_pdf_url in enumerate(chunk):
#             text += f"\n\nInvoice {number_chunk + k + 1}\n-----------------------------\n"

#             # --- FIX 5: Validate each URL in the chunk before fetching ---
#             if not each_pdf_url or not each_pdf_url.startswith('http'):
#                 print(f"Skipping invalid URL at index {k}: {each_pdf_url!r}")
#                 text += "[Skipped: invalid URL]\n"
#                 continue

#             pil_images = pdf_to_images(each_pdf_url, pages=page)
#             for img_idx, image in enumerate(pil_images):
#                 convert_text = pytesseract.image_to_string(image)
#                 text += f"Page {img_idx}\n\n{convert_text}"

#         number_chunk += max_chunk

#     return text


# def get_prompt(invoice_text: str, column: str):
#     client = OpenAI(
#     api_key="sk-a4b4bb56942c415e9129d84f52b5b391",
#     base_url="https://api.deepseek.com")

#     system_prompt = """
#         You are an invoice data extraction assistant. Your job is to extract user-specified fields from one or more invoices or credit notes and return them as a JSON array, where each object represents a single invoice.

#         The user will provide a list of column names to extract. You must:
#         1. Use EXACTLY the column names the user provides as the JSON keys.
#         2. Extract the corresponding value for each column from the invoice text.
#         3. Each object in the array represents one invoice or credit note.

#         Rules:
#         1. Return ONLY a valid JSON array — no markdown, no explanation, no preamble.
#         2. Even if only one invoice is provided, always return a JSON array with one object.
#         3. If a field cannot be found in a given invoice, set its value to null.
#         4. Clean up amounts: strip currency symbols and return them as numbers (e.g. 1241.45 not "£1,241.45").
#         5. Dates should be returned in ISO 8601 format (YYYY-MM-DD) where possible.
#         6. For address fields, return as a single string with commas separating each line.
#         7. Never guess or infer values that aren't explicitly in the text.
#         8. Only extract the columns the user specifies — do not add extra fields.

#         Example:

#         User provides columns: ["supplier_name", "total_amount", "invoice_date", "account_number"]

#         Expected output:
#         [
#         {
#             "supplier_name": "ENGIE Power Limited",
#             "total_amount": 1241.45,
#             "invoice_date": "2025-06-25",
#             "account_number": "11633129"
#         },
#         {
#             "supplier_name": "British Gas",
#             "total_amount": 340.00,
#             "invoice_date": "2025-05-10",
#             "account_number": "98271623"
#         }
#         ]
#     """

#     user_prompt = f"""
#     Extract the following columns from the invoice below:
#     {column}

#     Invoice text:
#     {invoice_text}
#     """
    
#     response = client.chat.completions.create(
#         model="deepseek-v4-flash",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         max_tokens=2000,
#         stream=False,
#         response_format={'type': 'json_object'},
#     )

#     if response.choices[0].message.content:
#         return json.loads(response.choices[0].message.content)
#     return [];


# def convert_to_excel(data: list[object], column: list[str]):
#     buffer = io.BytesIO()
#     dataFrame = pd.DataFrame(columns=column, data=data)
#     dataFrame.to_excel(buffer, index=False)
#     buffer.seek(0)
#     return base64.b64encode(buffer.getvalue()).decode("utf-8"),