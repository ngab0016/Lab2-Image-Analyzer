# Lab 2: Smart Image Analyzer with Durable Functions

**Course:** CST8917 - Serverless Applications  
**Semester:** Winter 2026  
**Student number:** 041196196

---

## Project Overview

This project implements a Smart Image Analyzer using Azure Durable Functions with the **Fan-Out/Fan-In pattern**. When an image is uploaded to Azure Blob Storage, the system automatically triggers and runs four different analyses in parallel, combines the results into a unified report, and stores it in Azure Table Storage.

### Key Features
- Automatic blob trigger on image upload
- Parallel execution of 4 analysis activities (Fan-Out/Fan-In)
- Real-time color analysis using Pillow
- Image metadata extraction (dimensions, format, EXIF data)
- Results stored in Azure Table Storage
- HTTP endpoint for retrieving analysis results

---

## Architecture

### Pattern: Fan-Out/Fan-In + Chaining

```
Image Upload → Blob Trigger → Orchestrator
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓               ↓
            analyze_colors  analyze_objects  analyze_text  analyze_metadata
                    ↓               ↓               ↓               ↓
                    └───────────────┼───────────────┘
                                    ↓
                            generate_report
                                    ↓
                             store_results
                                    ↓
                          Azure Table Storage
                                    ↓
                            get_results (HTTP)
```

### Functions Overview

| # | Function | Type | Purpose |
|---|----------|------|---------|
| 1 | `blob_trigger` | Client | Detects image upload, starts orchestrator |
| 2 | `image_analyzer_orchestrator` | Orchestrator | Coordinates parallel & sequential workflow |
| 3 | `analyze_colors` | Activity | Extracts dominant colors (real analysis) |
| 4 | `analyze_objects` | Activity | Detects objects (mock implementation) |
| 5 | `analyze_text` | Activity | Performs OCR (mock implementation) |
| 6 | `analyze_metadata` | Activity | Extracts real image metadata |
| 7 | `generate_report` | Activity | Combines all analyses into unified report |
| 8 | `store_results` | Activity | Saves report to Azure Table Storage |
| 9 | `get_results` | HTTP | Retrieves stored analysis results |

---

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- VS Code with Azure Functions Extension
- Azure Functions Core Tools
- Azure Storage Explorer (for testing)
- Azure subscription (for deployment)

### Local Setup

**1. Clone the repository**
```bash
git clone https://github.com/ngab0016/Lab2-Image-Analyzer.git
cd Lab2-Image-Analyzer
```

**2. Create and activate virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure local settings**
```bash
cp local.settings.example.json local.settings.json
```

The `local.settings.json` should contain:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "ImageStorageConnection": "UseDevelopmentStorage=true"
  },
  "Host": {
    "CORS": "*"
  }
}
```

**5. Start Azurite (local storage emulator)**
- In VS Code: Press `F1` → `Azurite: Start`
- Or via CLI: `azurite --silent --location .azurite`

**6. Create the `images` container**

Using Azure Storage Explorer:
- Connect to Local Emulator
- Right-click Blob Containers → Create Blob Container
- Name it `images`

**7. Start the Function App**
```bash
func start
```

---

## Testing Locally

### Upload an Image
1. Open Azure Storage Explorer
2. Navigate to Local Emulator → Blob Containers → images
3. Upload any image file (JPEG, PNG, etc.)

### View Logs
Watch the terminal for parallel execution:
```
Analyzing colors...
Analyzing objects...
Analyzing text (OCR)...
Analyzing metadata...
```

### Retrieve Results
Open your browser:
```
http://localhost:7071/api/results
```

Get a specific result by ID:
```
http://localhost:7071/api/results/{YOUR_RESULT_ID}
```

---

## Deployment to Azure

### 1. Create Function App in Azure

Using VS Code:
- Press `F1` → `Azure Functions: Create Function App in Azure... (Advanced)`
- Follow prompts to configure

### 2. Configure Environment Variables

In Azure Portal → Function App → Settings → Environment variables:

| Name | Value |
|------|-------|
| `AzureWebJobsStorage` | Your storage account connection string |
| `ImageStorageConnection` | Same storage account connection string |

### 3. Create `images` Container in Azure

Azure Portal → Storage Account → Containers → + Container → Name: `images`

### 4. Deploy from VS Code

- Press `F1` → `Azure Functions: Deploy to Function App`
- Select your function app
- Wait for deployment to complete

### 5. Test in Azure

Upload an image to the Azure `images` container, then visit:
```
https://YOUR-APP-NAME.azurewebsites.net/api/results
```

---

## Project Structure

```
Lab2-Image-Analyzer/
├── function_app.py              # All 9 functions
├── requirements.txt             # Python dependencies
├── host.json                    # Function app configuration
├── local.settings.json          # Local config (not committed)
├── local.settings.example.json  # Template for local settings
├── .gitignore                   # Git ignore rules
├── .funcignore                  # Function deployment ignore
└── README.md                    # This file
```

---

## Demo Video

**Video Link:** https://youtu.be/xRKJYSrcjzA

### Demo Contents:
- Local image upload and blob trigger firing
- Parallel execution logs (all 4 analyses starting simultaneously)
- Results retrieval via HTTP endpoint
- Azure deployment and cloud testing

---

## Sample Output

### Analysis Result Structure
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "fileName": "test-image.jpg",
  "analyzedAt": "2026-02-17T14:30:00.500000",
  "summary": {
    "imageSize": "1920x1080",
    "format": "JPEG",
    "dominantColor": "#404040",
    "objectsDetected": 3,
    "hasText": false,
    "isGrayscale": false
  },
  "analyses": {
    "colors": {
      "dominantColors": [
        {"hex": "#404040", "rgb": {"r": 64, "g": 64, "b": 64}, "percentage": 45.2}
      ],
      "isGrayscale": false
    },
    "objects": {
      "objects": [
        {"name": "landscape", "confidence": 0.85}
      ],
      "objectCount": 3
    },
    "text": {
      "hasText": false,
      "extractedText": ""
    },
    "metadata": {
      "width": 1920,
      "height": 1080,
      "format": "JPEG",
      "megapixels": 2.07,
      "sizeKB": 245.67
    }
  }
}
```

---

## Technologies Used

- **Azure Durable Functions** - Orchestration framework
- **Azure Blob Storage** - Image storage and trigger
- **Azure Table Storage** - Results persistence
- **Python 3.12** - Runtime environment
- **Pillow (PIL)** - Image processing library
- **Azurite** - Local storage emulator

---

## Key Learnings

### Fan-Out/Fan-In Pattern
The project demonstrates the power of parallel execution:
- **Sequential execution:** 4 analyses × 5 seconds = 20 seconds
- **Parallel execution:** 4 analyses simultaneously = ~5 seconds

### Durable Functions Benefits
- Automatic state management
- Built-in retry logic
- Orchestration replay capability
- Scalable parallel execution

---

## Security Notes

- `local.settings.json` contains sensitive connection strings and is excluded from version control
- Use `local.settings.example.json` as a template with placeholder values
- Never commit Azurite storage files (`__azurite_db_*`, `__blobstorage__/`, etc.)
- Rotate storage account keys if accidentally exposed


---

*Last Updated: February 17, 2026*
