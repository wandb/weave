---
title: Use an LLM to tag and caption images
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/tag_caption_images.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/tag_caption_images.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{cod-notebook} -->

*Adapted from the OpenAI Cookbook "[Using GPT4o mini to tag and caption images](https://cookbook.openai.com/examples/tag_caption_images_with_gpt4v)"*

# Use an LLM to tag & caption images

This notebook explores how to leverage the vision capabilities of the GPT-4* models (for example `gpt-4o`, `gpt-4o-mini` or `gpt-4-turbo`) to tag & caption images. 

We can leverage the multimodal capabilities of these models to provide input images along with additional context on what they represent, and prompt the model to output tags or image descriptions. The image descriptions can then be further refined with a language model (in this notebook, we'll use `gpt-4o-mini`) to generate captions. 

Generating text content from images can be useful for multiple use cases, especially use cases involving search.  
We will illustrate a search use case in this notebook by using generated keywords and product captions to search for products - both from a text input and an image input.

As an example, we will use a dataset of Amazon furniture items, tag them with relevant keywords and generate short, descriptive captions.

## Setup


```python
# Install dependencies if needed
%pip install --quiet openai scikit-learn pandas pillow
%pip install --quiet weave
```


```python
from IPython.display import display
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from openai import OpenAI

# Initializing OpenAI client - see https://platform.openai.com/docs/quickstart?context=python
# Define the OPENAI_API_KEY environment variable to simplify the initialization
client = OpenAI()
```


```python
# Loading dataset
import weave

# Retrieve the dataset
dataset = weave.ref(
    "weave:///team-jdoc/tag_caption_images/object/Amazon-Furniture-Dataset:latest"
).get()
df = pd.DataFrame(dataset.rows)
df.head()
```

## Tag images

In this section, we'll use GPT-4o mini to generate relevant tags for our products.

We'll use a simple zero-shot approach to extract keywords, and deduplicate those keywords using embeddings to avoid having multiple keywords that are too similar.

We will use a combination of an image and the product title to avoid extracting keywords for other items that are depicted in the image - sometimes there are multiple items used in the scene and we want to focus on just the one we want to tag.

### Extract keywords


```python
import requests
from PIL import Image
from io import BytesIO

def get_image(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return img

system_prompt = '''
    You are an agent specialized in tagging images of furniture items, decorative items, or furnishings with relevant keywords that could be used to search for these items on a marketplace.
    
    You will be provided with an image and the title of the item that is depicted in the image, and your goal is to extract keywords for only the item specified. 
    
    Keywords should be concise and in lower case. 
    
    Keywords can describe things like:
    - Item type e.g. 'sofa bed', 'chair', 'desk', 'plant'
    - Item material e.g. 'wood', 'metal', 'fabric'
    - Item style e.g. 'scandinavian', 'vintage', 'industrial'
    - Item color e.g. 'red', 'blue', 'white'
    
    Only deduce material, style or color keywords when it is obvious that they make the item depicted in the image stand out.

    Return keywords in the format of an array of strings, like this:
    ['desk', 'industrial', 'metal']
    
'''

@weave.op
def gen_keywords(img_url, title):
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_url,
                    }
                },
            ],
        },
        {
            "role": "user",
            "content": title
        }
    ],
        max_tokens=300,
        top_p=0.1
    )

    # return response.choices[0].message.content
    return {"keywords": response.choices[0].message.content, "image": get_image(img_url)}
```

#### Testing with a few examples


```python
examples = df.iloc[-5:]
```


```python
# Initialize tracing with weave
weave.init("tag_caption_images")

for index, ex in examples.iterrows():
    url = ex['primary_image']
    results = gen_keywords(url, ex['title'])
    display(results["image"])
    print(results["keywords"])
    print("\n\n")
```

### Looking up existing keywords

Using embeddings to avoid duplicates (synonyms) and/or match pre-defined keywords


```python
# Feel free to change the embedding model here
# @weave.op
def get_embedding(value, model="text-embedding-3-large"): 
    embeddings = client.embeddings.create(
      model=model,
      input=value,
      encoding_format="float"
    )
    return {"embedding": embeddings.data[0].embedding}
```

#### Testing with example keywords


```python
# Existing keywords
keywords_list = ["industrial", "metal", "wood", "vintage", "bed"]
```


```python
from weave import Dataset

keywords_embeddings = []
for keyword in keywords_list:
    item = {"embedding": get_embedding(keyword)["embedding"], "keyword": keyword}
    keywords_embeddings.append(item)

weave.publish(Dataset(name="keywords_embeddings", rows=keywords_embeddings))
```


```python
@weave.op
def compare_keyword(keyword, embeddings_ref):
    df_keywords = pd.DataFrame(embeddings_ref.get().rows)
    embedded_value = get_embedding(keyword)["embedding"]
    df_keywords['similarity'] = df_keywords['embedding'].apply(lambda x: cosine_similarity(np.array(x).reshape(1,-1), np.array(embedded_value).reshape(1, -1)))
    most_similar = df_keywords.sort_values('similarity', ascending=False).iloc[0]
    most_similar["similarity"] = most_similar["similarity"][0][0]
    return {
        "embedding": most_similar["embedding"],
        "keyword": most_similar["keyword"],
        "similarity": most_similar["similarity"]
    }


@weave.op
def replace_keyword(keyword, embeddings_ref, threshold=0.6):
    most_similar = compare_keyword(keyword, embeddings_ref)
    if most_similar['similarity'] > threshold:
        print(f"Replacing '{keyword}' with existing keyword: '{most_similar['keyword']}'")
        return {"keyword": most_similar['keyword']}
    return {"keyword": keyword}
```


```python
# Example keywords to compare to our list of existing keywords
example_keywords = ['bed frame', 'wooden', 'vintage', 'old school', 'desk', 'table', 'old', 'metal', 'metallic', 'woody']
final_keywords = []

for k in example_keywords:
    final_keywords.append(
        replace_keyword(k, weave.ref("keywords_embeddings:latest"))["keyword"]
    )

final_keywords = set(final_keywords)
print(f"Final keywords: {final_keywords}")
```

## Generate captions

In this section, we'll use GPT-4o mini to generate an image description and then use a few-shot examples approach with GPT-4-turbo to generate captions from the images.

If few-shot examples are not enough for your use case, consider fine-tuning a model to get the generated captions to match the style & tone you are targeting. 


```python
# Cleaning up dataset columns
selected_columns = ['title', 'primary_image', 'style', 'material', 'color', 'url']
df = df[selected_columns].copy()
df.head()
```

### Describing images with GPT-4o mini


```python
describe_system_prompt = '''
    You are a system generating descriptions for furniture items, decorative items, or furnishings on an e-commerce website.
    Provided with an image and a title, you will describe the main item that you see in the image, giving details but staying concise.
    You can describe unambiguously what the item is and its material, color, and style if clearly identifiable.
    If there are multiple items depicted, refer to the title to understand which item you should describe.
    '''

@weave.op
def describe_image(img_url, title):
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.2,
    messages=[
        {
            "role": "system",
            "content": describe_system_prompt
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_url,
                    }
                },
            ],
        },
        {
            "role": "user",
            "content": title
        }
    ],
    max_tokens=300,
    )

    return {"description": response.choices[0].message.content}
```

#### Testing on a few examples


```python
for index, row in examples.iterrows():
    print(f"{row['title'][:50]}{'...' if len(row['title']) > 50 else ''} - {row['url']} :")
    result = describe_image(row['primary_image'], row['title'])
    print(f"{result}\n--------------------------\n")
```

### Turning descriptions into captions
Using a few-shot examples approach to turn a long description into a short image caption


```python
caption_system_prompt = '''
Your goal is to generate short, descriptive captions for images of furniture items, decorative items, or furnishings based on an image description.
You will be provided with a description of an item image and you will output a caption that captures the most important information about the item.
Your generated caption should be short (1 sentence), and include the most relevant information about the item.
The most important information could be: the type of the item, the style (if mentioned), the material if especially relevant and any distinctive features.
'''

few_shot_examples = [
    {
        "description": "This is a multi-layer metal shoe rack featuring a free-standing design. It has a clean, white finish that gives it a modern and versatile look, suitable for various home decors. The rack includes several horizontal shelves dedicated to organizing shoes, providing ample space for multiple pairs. Above the shoe storage area, there are 8 double hooks arranged in two rows, offering additional functionality for hanging items such as hats, scarves, or bags. The overall structure is sleek and space-saving, making it an ideal choice for placement in living rooms, bathrooms, hallways, or entryways where efficient use of space is essential.",
        "caption": "White metal free-standing shoe rack"
    },
    {
        "description": "The image shows a set of two dining chairs in black. These chairs are upholstered in a leather-like material, giving them a sleek and sophisticated appearance. The design features straight lines with a slight curve at the top of the high backrest, which adds a touch of elegance. The chairs have a simple, vertical stitching detail on the backrest, providing a subtle decorative element. The legs are also black, creating a uniform look that would complement a contemporary dining room setting. The chairs appear to be designed for comfort and style, suitable for both casual and formal dining environments.",
        "caption": "Set of 2 modern black leather dining chairs"
    },
    {
        "description": "This is a square plant repotting mat designed for indoor gardening tasks such as transplanting and changing soil for plants. It measures 26.8 inches by 26.8 inches and is made from a waterproof material, which appears to be a durable, easy-to-clean fabric in a vibrant green color. The edges of the mat are raised with integrated corner loops, likely to keep soil and water contained during gardening activities. The mat is foldable, enhancing its portability, and can be used as a protective surface for various gardening projects, including working with succulents. It's a practical accessory for garden enthusiasts and makes for a thoughtful gift for those who enjoy indoor plant care.",
        "caption": "Waterproof square plant repotting mat"
    }
]

formatted_examples = [[{
    "role": "user",
    "content": ex['description']
},
{
    "role": "assistant", 
    "content": ex['caption']
}]
    for ex in few_shot_examples
]

formatted_examples = [i for ex in formatted_examples for i in ex]
for item in formatted_examples:
    print(item)

```


```python
@weave.op
def caption_image(formatted_examples, description: str, model="gpt-4o-mini"):
    messages = formatted_examples
    messages.insert(0, 
        {
            "role": "system",
            "content": caption_system_prompt
        })
    messages.append(
        {
            "role": "user",
            "content": description
        })
    response = client.chat.completions.create(
    model=model,
    temperature=0.2,
    messages=messages
    )

    return {
        "caption": response.choices[0].message.content,
        "message_count": len(messages),
    }
```

#### Testing on a few examples


```python
examples = df.iloc[5:8]
```


```python
for index, row in examples.iterrows():
    print(f"{row['title'][:50]}{'...' if len(row['title']) > 50 else ''} - {row['url']} :")
    result = describe_image(row["primary_image"], row["title"])
    print(f"{result}")
    img_caption = caption_image(formatted_examples, result["description"])
    print(f"{img_caption}\n--------------------------\n")
```

## Image search

In this section, we will use generated keywords and captions to search items that match a given input, either text or image.

We will leverage our embeddings model to generate embeddings for the keywords and captions and compare them to either input text or the generated caption from an input image.


```python
# Df we'll use to compare keywords
df['keywords'] = ''
df['img_description'] = ''
df['caption'] = ''
df.head()
```


```python
# Function to replace a keyword with an existing keyword if it's too similar
@weave.op
def get_keyword(keyword, embeddings_ref, threshold=0.6):
    embedded_value = get_embedding(keyword)["embedding"]
    df_keywords = pd.DataFrame(embeddings_ref.get().rows)
    df_keywords['similarity'] = df_keywords['embedding'].apply(lambda x: cosine_similarity(np.array(x).reshape(1,-1), np.array(embedded_value).reshape(1, -1)))
    sorted_keywords = df_keywords.copy().sort_values('similarity', ascending=False)
    if len(sorted_keywords) > 0 :
        most_similar = sorted_keywords.iloc[0]
        if most_similar['similarity'] > threshold:
            print(f"Replacing '{keyword}' with existing keyword: '{most_similar['keyword']}'")
            return {"keyword": most_similar['keyword']}
    new_keyword = {
        'keyword': keyword,
        'embedding': embedded_value
    }
    df_keywords = pd.concat([df_keywords, pd.DataFrame([new_keyword])], ignore_index=True)
    return {"keyword": keyword}
```

### Preparing the dataset


```python
import ast


@weave.op
def tag_and_caption(row, embeddings_ref):
    df_keywords = pd.DataFrame(embeddings_ref.get().rows)
    keywords = gen_keywords(row["primary_image"], row["title"])["keywords"]
    try:
        keywords = ast.literal_eval(keywords.strip())
        mapped_keywords = [
            get_keyword(k, weave.ref("keywords_embeddings:latest"))["keyword"]
            for k in keywords
        ]
    except Exception as e:
        print(f"Error parsing keywords: {keywords}")
        mapped_keywords = []
    img_description = describe_image(row['primary_image'], row['title'])["description"]
    caption = caption_image(formatted_examples, img_description)["caption"]
    return {
        'keywords': mapped_keywords,
        'img_description': img_description,
        'caption': caption
    }
```


```python
df.shape
```

Processing all 312 lines of the dataset will take a while.
To test out the idea, we will only run it on the first 5 lines. 
Feel free to skip this step and load the already processed dataset (see below).


```python
# Running on first 5 lines
for index, row in df[:5].iterrows():
    print(
        f"{index} - {row['title'][:50]}{'...' if len(row['title']) > 50 else ''}"
    )
    updates = tag_and_caption(row, weave.ref("keywords_embeddings:latest"))
    df.loc[index, updates.keys()] = updates.values()
```


```python
# Save to weave - optional: uncomment if you processed the whole dataset
# weave.publish(
#     Dataset(name="Tagged-and-Captioned-Items", rows=df.to_dict(orient="records"))
# )
```


```python
# Load data from weave
df = weave.ref("Tagged-and-Captioned-Items:latest").get()
df = pd.DataFrame(df.rows)
df.head()
```

### Embedding captions and keywords
We can now use the generated captions and keywords to match relevant content to an input text query or caption. 
To do this, we will embed a combination of keywords + captions.
Note: creating the embeddings will take ~3 mins to run. Feel free to load the pre-processed dataset (see below).


```python
df_search = df.copy()
```


```python
def embed_tags_caption(x):
    if x['caption'] != '':
        try:
            keywords_string = ",".join(k for k in x['keywords']) + '\n'
            content = keywords_string + x['caption']
            embedding = get_embedding(content)
            return embedding
        except Exception as e:
            print(f"Error creating embedding for {x}: {e}")
```


```python
df_search['embedding'] = df_search.apply(lambda x: embed_tags_caption(x), axis=1)
```


```python
df_search.head()
```


```python
# Keep only the lines where we have embeddings
df_search = df_search.dropna(subset=['embedding'])
print(df_search.shape)
```


```python
# Optional: save to weave for later
# weave.publish(
#     Dataset(name="Tagged-and-Captioned-Embeddings", rows=df_search.to_dict(orient="records"))
# )
```

### Search from input text    

We can compare the input text from a user directly to the embeddings we just created.


```python
from ast import literal_eval

# Searching for N most similar results
@weave.op
def search_from_input_text(query, search_embeddings_ref, n = 2):
    embedded_value = get_embedding(query)["embedding"]
    df_search = pd.DataFrame(search_embeddings_ref.get().rows)
    df_search["embedding"] = df_search.embedding.apply(literal_eval).apply(np.array)
    df_search['similarity'] = df_search['embedding'].apply(lambda x: cosine_similarity(np.array(x).reshape(1,-1), np.array(embedded_value).reshape(1, -1)))
    most_similar = df_search.sort_values('similarity', ascending=False).iloc[:n]
    return {"most_similar": most_similar}
```


```python
user_inputs = ['shoe storage', 'black metal side table', 'doormat', 'step bookshelf', 'ottoman']
```


```python
for i in user_inputs:
    print(f"Input: {i}\n")
    res = search_from_input_text(i, weave.ref("Tagged-and-Captioned-Embeddings:latest"))[
        "most_similar"
    ]
    for index, row in res.iterrows():
        similarity_score = row['similarity']
        if isinstance(similarity_score, np.ndarray):
            similarity_score = similarity_score[0][0]
        print(f"{row['title'][:50]}{'...' if len(row['title']) > 50 else ''} ({row['url']}) - Similarity: {similarity_score:.2f}")
        img = get_image(row['primary_image'])
        display(img)
        print("\n\n")
```

### Search from image

If the input is an image, we can find similar images by first turning images into captions, and embedding those captions to compare them to the already created embeddings.


```python
# We'll take a mix of images: some we haven't seen and some that are already in the dataset
example_images = df.iloc[306:309]['primary_image'].to_list() + df.iloc[1:4]['primary_image'].to_list()
```


```python
@weave.op
def search_from_image(image, image_url, search_embeddings_ref, n = 1):
    img_description = describe_image(image_url, "")["description"]
    caption = caption_image(formatted_examples, img_description)["caption"]
    res = search_from_input_text(caption, search_embeddings_ref, 1)["most_similar"].iloc[0]
    similarity_score = res["similarity"]
    if isinstance(similarity_score, np.ndarray):
        similarity_score = similarity_score[0][0]
    print(
        f"{res['title'][:50]}{'...' if len(res['title']) > 50 else ''} ({res['url']}) - Similarity: {similarity_score:.2f}"
    )
    img_res = get_image(res["primary_image"])
    return {"image": img_res}

```


```python
for url in example_images:
    img = get_image(url)
    search_from_image(img, url, weave.ref("Tagged-and-Captioned-Embeddings:latest"))
```

## Wrapping up


In this notebook, we explored how to leverage the multimodal capabilities of `gpt-4o-mini` to tag and caption images. By providing images along with contextual information to the model, we were able to generate tags and descriptions that can be further refined to create captions. This process has practical applications in various scenarios, particularly in enhancing search functionalities.

The search use case illustrated can be directly applied to applications such as recommendation systems, but the techniques covered in this notebook can be extended beyond items search and used in multiple use cases, for example RAG applications leveraging unstructured image data.

As a next step, you could explore using a combination of rule-based filtering with keywords and embeddings search with captions to retrieve more relevant results.
