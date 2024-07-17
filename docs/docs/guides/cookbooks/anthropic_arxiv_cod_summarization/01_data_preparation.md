
# Data Preparation for Arxiv PDF Summarization
In this section, we'll set up our environment and prepare the data for our Arxiv PDF summarization bot. We'll focus on fetching papers from Arxiv, extracting their content, and preparing it for summarization by loading the PDF, extracting images, and processing them.

## Step 1: Environment Setup

First, let's import the necessary libraries:

```python
import arxiv
import io
import anthropic
import os
from dotenv import load_dotenv
import base64
import requests
from tqdm import tqdm
import PyPDF2
import re
import weave
from arxiv_models import convert_raw_arxiv_to_pydantic
import filetype
from PIL import Image
from pdf2image import convert_from_bytes
from datetime import datetime, timezone
from arxiv_models import ArxivPaper, Author, Link
```

Install these libraries using pip if you haven't already:

```bash
pip install arxiv anthropic python-dotenv requests tqdm PyPDF2 weave filetype pillow pdf2image
```

## Step 2: Load Environment Variables

We'll use environment variables to securely store our API keys. Create a `.env` file in your project directory and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

Then, load the environment variables:

```python
load_dotenv()
```

## Step 3: Initialize Weave and Anthropic Client

Set up Weave for experiment tracking and the Anthropic client for accessing the LLM:

```python
weave.init("arxiv-papers-anthropic-summarization")
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

## Step 4: Generate Arxiv Query

In our Arxiv PDF summarization bot, we need an effective way to fetch relevant papers based on the user's research interests or specific topics. Instead of relying on predefined queries or manual input, we'll leverage the power of the large language model (LLM) to generate optimal Arxiv queries.

This approach offers several advantages in our summarization pipeline:

1. **Tailored searches**: The LLM can interpret natural language instructions and convert them into well-formed Arxiv queries, allowing users to describe their research interests in plain language.

2. **Query optimization**: The model can apply its knowledge of academic research and Arxiv's search syntax to create queries that are more likely to return relevant results.

3. **Adaptability**: As research trends evolve, the LLM can adjust its query generation strategy without requiring manual updates to our code.

4. **Handling complex topics**: For multidisciplinary or niche topics, the LLM can generate queries that combine multiple concepts or use appropriate synonyms to improve search results.

We'll use the LLM to generate an optimal Arxiv query based on a given instruction:


```python
@weave.op()
def generate_arxiv_query_args(instruction, model="claude-3-sonnet-20240229"):
    tools = [{
        "name": "prepare_arxiv_search",
        "description": "Prepare arguments for ArXiv paper search...",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The ArXiv search query string..."
                },
                "max_results": {
                    "type": "integer",
                    "description": "The maximum number of paper results to return..."
                }
            },
            "required": ["query", "max_results"]
        }
    }]

    system_prompt = "You are an expert at generating ArXiv queries..."

    messages = [
        {
            "role": "user",
            "content": f"Use the prepare_arxiv_search tool to generate an optimal ArXiv query and determine the maximum number of results for the following research instruction: {instruction}"
        }
    ]

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        messages=messages,
        system=system_prompt,
        tools=tools
    )

    for content in response.content:
        if content.type == 'tool_use' and content.name == 'prepare_arxiv_search':
            args = content.input
            return args.get('query'), args.get('max_results')

    return f"{instruction}", 5
```

## Step 5: Fetch Arxiv Papers

Now let's create a function to fetch papers from Arxiv using the generated query:

```python
@weave.op()
def fetch_arxiv_papers(query, max_results=5):
    arxiv_client = arxiv.Client()
    
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
        sort_order=arxiv.SortOrder.Descending
    )
    
    papers = []
    for result in arxiv_client.results(search):
        paper = convert_raw_arxiv_to_pydantic(result)
        papers.append(paper)
    
    return papers
```

## Step 6: Process PDF Content

We'll create a function to load the PDF content:

```python
def load_pdf(arxiv_result):
    pdf_url = arxiv_result["pdf_url"]
    response = requests.get(pdf_url)
    pdf_file = io.BytesIO(response.content)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    return pdf_reader
```

## Step 7: Prepare Data for Summarization

Finally, we'll create a sample paper and prepare the dataset for our summarization task:

```python
arxiv_paper = ArxivPaper(
    entry_id="http://arxiv.org/abs/2406.04744v1",
    updated=datetime(2024, 6, 7, 8, 43, 7, tzinfo=timezone.utc),
    published=datetime(2024, 6, 7, 8, 43, 7, tzinfo=timezone.utc),
    title="CRAG -- Comprehensive RAG Benchmark",
    authors=[
        Author(full_name="Xiao Yang"),
        Author(full_name="Kai Sun"),
        # ... other authors ...
    ],
    summary="Retrieval-Augmented Generation (RAG) has recently emerged as a promising solution...",
    comment="",
    journal_ref=None,
    doi="10.48550/arXiv.2406.04744",
    primary_category="cs.CL",
    categories=["cs.CL"],
    links=[
        Link(href="https://arxiv.org/abs/2406.04744", title="Abstract", rel="alternate", content_type=None),
        Link(href="https://arxiv.org/pdf/2406.04744", title="pdf", rel="related", content_type=None)
    ],
    pdf_url="https://arxiv.org/pdf/2406.04744"
)
```

## Step 8: Extract Images from PDF

In scientific papers, figures, diagrams, and charts often convey crucial information that complements the text. To create comprehensive summaries, our Arxiv PDF summarization bot needs to process both textual and visual content. We'll create functions to extract and analyze images from the PDF files, enhancing the overall quality of our summaries.

This step involves several key components:

1. **Image Extraction**: We'll extract both raster images and vector graphics from the PDF files.

2. **Vector Graphic Conversion**: Since vector graphics are not directly viewable, we'll convert them to raster images for processing. This is done by converting the PDF to an image and resizing it.

3. **Image Analysis**: We'll use the Anthropic LLM to generate detailed technical descriptions of each extracted image.

Here are the main functions we'll implement:


```python
def convert_vector_graphic_page_to_image(pdf_page, scale_factor=0.5):
    def get_object(obj):
        if isinstance(obj, PyPDF2.generic.IndirectObject):
            return obj.get_object()
        return obj

    resources = get_object(pdf_page.get('/Resources', {}))
    xobject = get_object(resources.get('/XObject', {}))
    
    # Check if there's a figure that's not an image
    if xobject:
        for obj in xobject.values():
            obj = get_object(obj)
            if isinstance(obj, dict) and obj.get('/Subtype') == '/Form':  # This indicates a vector graphic
                # Convert the page to a PIL Image
                pdf_bytes = io.BytesIO()
                pdf_writer = PyPDF2.PdfWriter()
                pdf_writer.add_page(pdf_page)
                pdf_writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                
                # Convert PDF to image
                images = convert_from_bytes(pdf_bytes.getvalue(), fmt='png')
                
                if images:
                    image = images[0]
                    # Resize the image
                    new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
                    image = image.resize(new_size, Image.LANCZOS)
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    img_str = base64.b64encode(img_byte_arr).decode("utf-8")
                    data_url = f"data:image/png;base64,{img_str}"
                    return data_url
    
    return None  # Return None if no conversion was needed

@weave.op()
def process_figure_image(data_url, model="claude-3-5-sonnet-20240620"):
    """Process image data and return a detailed technical description."""
    img_str = data_url.split(",")[1]

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_str,
                        },
                    },
                    {
                        "type": "text",
                        "text": """Analyze this image as if it's a figure from a scientific research paper. Provide a detailed technical description addressing the following:

1. Type of figure (e.g., graph, diagram, flowchart, experimental setup)
2. Key components or variables represented
3. Relationships or trends depicted
4. Quantitative information (if present)
5. Methodology or process illustrated (if applicable)
6. Potential implications or conclusions that can be drawn
7. Any limitations or assumptions evident in the figure

Focus on technical accuracy and relevance to scientific research. Avoid general descriptions and concentrate on the specific scientific content presented.""",
                    },
                ],
            }
        ],
    )
    return response.content[0].text

@weave.op()
def extract_images(paper, model="claude-3-5-sonnet-20240620"):
    """Extract text and images from PDF content."""

    pdf_reader = load_pdf(paper)

    all_images = []

    for page in pdf_reader.pages:
        images = []

        for image in page.images:
            img_data = image.data
            kind = filetype.guess(img_data)
            if kind is None:
                print(f"Cannot guess file type!")
                continue
            
            img_str = base64.b64encode(img_data).decode("utf-8")
            data_url = f"data:{kind.mime};base64,{img_str}"
            try:
                images.append(
                    {"image": data_url, "description": process_figure_image(data_url, model=model)}
                )
            except Exception as e:
                print(f"Error processing image: {e}")
                images.append({"image": data_url, "description": ""})
        
        vector_graphics_image_data_url = convert_vector_graphic_page_to_image(page)
        if vector_graphics_image_data_url:
            images.append({"image": vector_graphics_image_data_url, "description": process_vector_image_pdf(vector_graphics_image_data_url, model=model)})
        all_images.append(images)

    return all_images
```

These functions work together to:

1. Identify and extract both raster images and vector graphics from each page of the PDF.
2. Convert vector graphics to viewable images.
3. Encode images as base64 strings for easy transmission and processing.
4. Use the Anthropic LLM to generate detailed technical descriptions of each image, focusing on scientific content and relevance.

By incorporating image extraction and analysis, our summarization bot gains several advantages:

- **Comprehensive Understanding**: The bot can provide summaries that include insights from both text and visual elements of the paper.
- **Enhanced Context**: Image descriptions can clarify complex concepts or experimental setups that might be difficult to understand from text alone.
- **Multi-modal Summarization**: The ability to process both text and images allows for more nuanced and informative summaries.

This image processing capability significantly enhances our summarization pipeline, allowing researchers to quickly grasp key visual information without needing to manually inspect each figure in the original paper.
