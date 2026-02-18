# =============================================================================
# IMPORTS
# =============================================================================
import azure.functions as func
import azure.durable_functions as df
from azure.data.tables import TableServiceClient, TableClient
from PIL import Image
import logging
import json
import io
import os
import uuid
from datetime import datetime

# =============================================================================
# CREATE THE DURABLE FUNCTION APP
# =============================================================================
myApp = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# =============================================================================
# TABLE STORAGE HELPER
# =============================================================================
TABLE_NAME = "ImageAnalysisResults"

def get_table_client():
    """Get a TableClient for storing/retrieving analysis results."""
    connection_string = os.environ["ImageStorageConnection"]
    table_service = TableServiceClient.from_connection_string(connection_string)
    table_service.create_table_if_not_exists(TABLE_NAME)
    return table_service.get_table_client(TABLE_NAME)

# =============================================================================
# 1. CLIENT FUNCTION (Blob Trigger)
# =============================================================================
@myApp.blob_trigger(
    arg_name="myblob",
    path="images/{name}",
    connection="ImageStorageConnection"
)
@myApp.durable_client_input(client_name="client")
async def blob_trigger(myblob: func.InputStream, client):
    blob_name = myblob.name
    blob_bytes = myblob.read()
    blob_size_kb = round(len(blob_bytes) / 1024, 2)

    logging.info(f"New image detected: {blob_name} ({blob_size_kb} KB)")

    input_data = {
        "blob_name": blob_name,
        "blob_bytes": list(blob_bytes),
        "blob_size_kb": blob_size_kb
    }

    instance_id = await client.start_new(
        "image_analyzer_orchestrator",
        client_input=input_data
    )

    logging.info(f"Started orchestration {instance_id} for {blob_name}")

# =============================================================================
# 2. ORCHESTRATOR FUNCTION
# =============================================================================
@myApp.orchestration_trigger(context_name="context")
def image_analyzer_orchestrator(context):
    input_data = context.get_input()

    logging.info(f"Orchestrator started for: {input_data['blob_name']}")

    # STEP 1: FAN-OUT - Run all 4 analyses in parallel
    analysis_tasks = [
        context.call_activity("analyze_colors", input_data),
        context.call_activity("analyze_objects", input_data),
        context.call_activity("analyze_text", input_data),
        context.call_activity("analyze_metadata", input_data),
    ]

    # FAN-IN - Wait for ALL tasks to complete
    results = yield context.task_all(analysis_tasks)

    # STEP 2: CHAIN - Generate report
    report_input = {
        "blob_name": input_data["blob_name"],
        "colors": results[0],
        "objects": results[1],
        "text": results[2],
        "metadata": results[3],
    }

    report = yield context.call_activity("generate_report", report_input)

    # STEP 3: CHAIN - Store results
    record = yield context.call_activity("store_results", report)

    return record

# =============================================================================
# 3. ACTIVITY: Analyze Colors
# =============================================================================
@myApp.activity_trigger(input_name="inputData")
def analyze_colors(inputData: dict):
    logging.info("Analyzing colors...")

    try:
        image_bytes = bytes(inputData["blob_bytes"])
        image = Image.open(io.BytesIO(image_bytes))

        if image.mode != "RGB":
            image = image.convert("RGB")

        small_image = image.resize((50, 50))
        pixels = list(small_image.getdata())

        color_counts = {}
        for r, g, b in pixels:
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            color_counts[key] = color_counts.get(key, 0) + 1

        sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
        top_colors = []
        for (r, g, b), count in sorted_colors[:5]:
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            top_colors.append({
                "hex": hex_color,
                "rgb": {"r": r, "g": g, "b": b},
                "percentage": round(count / len(pixels) * 100, 1)
            })

        grayscale_pixels = sum(1 for r, g, b in pixels if abs(r - g) < 30 and abs(g - b) < 30)
        is_grayscale = grayscale_pixels / len(pixels) > 0.9

        return {
            "dominantColors": top_colors,
            "isGrayscale": is_grayscale,
            "totalPixelsSampled": len(pixels)
        }

    except Exception as e:
        logging.error(f"Color analysis failed: {str(e)}")
        return {
            "dominantColors": [],
            "isGrayscale": False,
            "totalPixelsSampled": 0,
            "error": str(e)
        }

# =============================================================================
# 4. ACTIVITY: Analyze Objects (Mock)
# =============================================================================
@myApp.activity_trigger(input_name="inputData")
def analyze_objects(inputData: dict):
    logging.info("Analyzing objects...")

    try:
        image_bytes = bytes(inputData["blob_bytes"])
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size

        mock_objects = []

        if width > height:
            mock_objects.append({"name": "landscape", "confidence": 0.85})
        elif height > width:
            mock_objects.append({"name": "portrait", "confidence": 0.82})
        else:
            mock_objects.append({"name": "square composition", "confidence": 0.90})

        if width * height > 1000000:
            mock_objects.append({"name": "high-resolution scene", "confidence": 0.78})

        mock_objects.append({"name": "digital image", "confidence": 0.99})

        return {
            "objects": mock_objects,
            "objectCount": len(mock_objects),
            "note": "Mock analysis - replace with Azure Computer Vision for real detection"
        }

    except Exception as e:
        logging.error(f"Object analysis failed: {str(e)}")
        return {
            "objects": [],
            "objectCount": 0,
            "error": str(e)
        }

# =============================================================================
# 5. ACTIVITY: Analyze Text / OCR (Mock)
# =============================================================================
@myApp.activity_trigger(input_name="inputData")
def analyze_text(inputData: dict):
    logging.info("Analyzing text (OCR)...")

    try:
        image_bytes = bytes(inputData["blob_bytes"])
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size

        return {
            "hasText": False,
            "extractedText": "",
            "confidence": 0.0,
            "language": "unknown",
            "note": "Mock OCR - replace with Azure Computer Vision Read API for real text extraction"
        }

    except Exception as e:
        logging.error(f"Text analysis failed: {str(e)}")
        return {
            "hasText": False,
            "extractedText": "",
            "confidence": 0.0,
            "error": str(e)
        }

# =============================================================================
# 6. ACTIVITY: Analyze Metadata (Real)
# =============================================================================
@myApp.activity_trigger(input_name="inputData")
def analyze_metadata(inputData: dict):
    logging.info("Analyzing metadata...")

    try:
        image_bytes = bytes(inputData["blob_bytes"])
        blob_size_kb = inputData["blob_size_kb"]
        image = Image.open(io.BytesIO(image_bytes))

        width, height = image.size
        total_pixels = width * height

        exif_data = {}
        try:
            raw_exif = image._getexif()
            if raw_exif:
                from PIL.ExifTags import TAGS
                for tag_id, value in raw_exif.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if isinstance(value, (str, int, float)):
                        exif_data[str(tag_name)] = str(value)
        except (AttributeError, Exception):
            pass

        return {
            "width": width,
            "height": height,
            "format": image.format or "Unknown",
            "mode": image.mode,
            "totalPixels": total_pixels,
            "megapixels": round(total_pixels / 1000000, 2),
            "sizeKB": blob_size_kb,
            "aspectRatio": f"{width}:{height}",
            "hasExifData": len(exif_data) > 0,
            "exifData": exif_data
        }

    except Exception as e:
        logging.error(f"Metadata analysis failed: {str(e)}")
        return {
            "width": 0,
            "height": 0,
            "format": "Unknown",
            "error": str(e)
        }

# =============================================================================
# 7. ACTIVITY: Generate Report
# =============================================================================
@myApp.activity_trigger(input_name="reportData")
def generate_report(reportData: dict):
    logging.info("Generating combined report...")

    blob_name = reportData["blob_name"]
    filename = blob_name.split("/")[-1] if "/" in blob_name else blob_name

    report = {
        "id": str(uuid.uuid4()),
        "fileName": filename,
        "blobPath": blob_name,
        "analyzedAt": datetime.utcnow().isoformat(),
        "analyses": {
            "colors": reportData["colors"],
            "objects": reportData["objects"],
            "text": reportData["text"],
            "metadata": reportData["metadata"],
        },
        "summary": {
            "imageSize": f"{reportData['metadata'].get('width', 0)}x{reportData['metadata'].get('height', 0)}",
            "format": reportData["metadata"].get("format", "Unknown"),
            "dominantColor": reportData["colors"]["dominantColors"][0]["hex"] if reportData["colors"].get("dominantColors") else "N/A",
            "objectsDetected": reportData["objects"].get("objectCount", 0),
            "hasText": reportData["text"].get("hasText", False),
            "isGrayscale": reportData["colors"].get("isGrayscale", False),
        }
    }

    logging.info(f"Report generated: {report['id']}")
    return report

# =============================================================================
# 8. ACTIVITY: Store Results
# =============================================================================
@myApp.activity_trigger(input_name="report")
def store_results(report: dict):
    logging.info(f"Storing results for {report['fileName']}...")

    try:
        table_client = get_table_client()

        entity = {
            "PartitionKey": "ImageAnalysis",
            "RowKey": report["id"],
            "FileName": report["fileName"],
            "BlobPath": report["blobPath"],
            "AnalyzedAt": report["analyzedAt"],
            "Summary": json.dumps(report["summary"]),
            "ColorAnalysis": json.dumps(report["analyses"]["colors"]),
            "ObjectAnalysis": json.dumps(report["analyses"]["objects"]),
            "TextAnalysis": json.dumps(report["analyses"]["text"]),
            "MetadataAnalysis": json.dumps(report["analyses"]["metadata"]),
        }

        table_client.upsert_entity(entity)
        logging.info(f"Results stored with ID: {report['id']}")

        return {
            "id": report["id"],
            "fileName": report["fileName"],
            "status": "stored",
            "analyzedAt": report["analyzedAt"],
            "summary": report["summary"]
        }

    except Exception as e:
        logging.error(f"Failed to store results: {str(e)}")
        return {
            "id": report.get("id", "unknown"),
            "status": "error",
            "error": str(e)
        }

# =============================================================================
# 9. HTTP FUNCTION: Get Results
# =============================================================================
@myApp.route(route="results/{id?}")
def get_results(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Get results endpoint called")

    try:
        table_client = get_table_client()
        result_id = req.route_params.get("id")

        if result_id:
            try:
                entity = table_client.get_entity(
                    partition_key="ImageAnalysis",
                    row_key=result_id
                )

                result = {
                    "id": entity["RowKey"],
                    "fileName": entity["FileName"],
                    "blobPath": entity["BlobPath"],
                    "analyzedAt": entity["AnalyzedAt"],
                    "summary": json.loads(entity["Summary"]),
                    "analyses": {
                        "colors": json.loads(entity["ColorAnalysis"]),
                        "objects": json.loads(entity["ObjectAnalysis"]),
                        "text": json.loads(entity["TextAnalysis"]),
                        "metadata": json.loads(entity["MetadataAnalysis"]),
                    }
                }

                return func.HttpResponse(
                    json.dumps(result, indent=2),
                    mimetype="application/json",
                    status_code=200
                )

            except Exception:
                return func.HttpResponse(
                    json.dumps({"error": f"Result not found: {result_id}"}),
                    mimetype="application/json",
                    status_code=404
                )
        else:
            limit = int(req.params.get("limit", "10"))

            entities = table_client.query_entities(
                query_filter="PartitionKey eq 'ImageAnalysis'"
            )

            results = []
            for entity in entities:
                results.append({
                    "id": entity["RowKey"],
                    "fileName": entity["FileName"],
                    "analyzedAt": entity["AnalyzedAt"],
                    "summary": json.loads(entity["Summary"]),
                })

            results.sort(key=lambda x: x["analyzedAt"], reverse=True)
            results = results[:limit]

            return func.HttpResponse(
                json.dumps({"count": len(results), "results": results}, indent=2),
                mimetype="application/json",
                status_code=200
            )

    except Exception as e:
        logging.error(f"Failed to retrieve results: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )