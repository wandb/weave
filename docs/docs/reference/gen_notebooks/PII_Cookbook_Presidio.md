---
title: PII Cookbook Presidio
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/PII_Cookbook_Presidio.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/PII_Cookbook_Presidio.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{cod-notebook} -->

# How to use Weave with PII data:

In this tutorial, we'll demonstrate how to utilize Weave while preventing your Personally Identifiable Information (PII) data from being incorporated into Weave or the LLMs you employ.

To protect our PII data, we'll employ Microsoft's [Presidio](https://microsoft.github.io/presidio/), a Python-based data protection SDK. This tool provides redaction and replacement functionalities, both of which we will implement in this tutorial.

For this use-case. We will leverage Anthropic's claude-3-sonnet to perform sentiment analysis. While we use Weave's [Traces](https://wandb.github.io/weave/quickstart) to track and analize the LLM's API calls. Sonnet will receive block of text and output one of the following sentiment classification:
1. positive
2. negative
3. neutral


```python
# @title required python packages:
!pip install presidio_analyzer
!pip install presidio_anonymizer
!python -m spacy download en_core_web_lg # Presidio uses spacy NLP engine
!pip install Faker                       # we'll use Faker to replace PII data with fake data
!pip install weave                        # To leverage Traces
!pip install set-env-colab-kaggle-dotenv -q # for env var
!pip install anthropic                      # to use sonnet
```

# Method 1A:
Our first method involves complete removal of PII data using Presidio. This approach redacts PII and replaces it with a placeholder representing the PII type. For example:
```
 "My name is Alex"
```

Will be:

```
 "My name is <PERSON>"
```
Presidio comes with a built-in [list of recognizable entities](https://microsoft.github.io/presidio/supported_entities/). We can select the ones that are important for our use case. In the below example, we are only looking at redicating names and phone numbers from our text:


```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

text= "My phone number is 212-555-5555 and my name is alex"

# Set up the engine, loads the NLP module (spaCy model by default)
# and other PII recognizers
analyzer = AnalyzerEngine()

# Call analyzer to get results
results = analyzer.analyze(text=text,
                           entities=["PHONE_NUMBER", "PERSON"],
                           language='en')

# Analyzer results are passed to the AnonymizerEngine for anonymization

anonymizer = AnonymizerEngine()

anonymized_text = anonymizer.anonymize(text=text,analyzer_results=results)

print(anonymized_text)
```

Let's encapsulate the previous step into a function and expand the entity recognition capabilities. We will expand our redaction scope to include addresses, email addresses, and US Social Security numbers.


```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
"""
The below function will take a block of text, process it using presidio
and return a block of text with the PII data redicated.
PII data to be redicated:
- Phone Numbers
- Names
- Addresses
- Email addresses
- US Social Security Numbers
"""
def anonymize_my_text(text):
  results = analyzer.analyze(text=text,
                           entities=["PHONE_NUMBER", "PERSON", "LOCATION", "EMAIL_ADDRESS","US_SSN"],
                           language='en')
  anonymized_text = anonymizer.anonymize(text=text,analyzer_results=results)
  return anonymized_text.text
```

    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - CreditCardRecognizer supported languages: es, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - CreditCardRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - CreditCardRecognizer supported languages: pl, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - EsNifRecognizer supported languages: es, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - EsNieRecognizer supported languages: es, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - ItDriverLicenseRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - ItFiscalCodeRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - ItVatCodeRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - ItIdentityCardRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - ItPassportRecognizer supported languages: it, registry supported languages: en
    WARNING:presidio-analyzer:Recognizer not added to registry because language is not supported by registry - PlPeselRecognizer supported languages: pl, registry supported languages: en


**Now we start building our tracing using Weave's Traces:**





Let's load our initial PII data. For demonstration purposes, we'll use a dataset containing 10 text blocks. A larger dataset with 1000 entries is available at [link].




```python
import json
with open('10_pii_data.json') as f:
    pii_data = json.load(f)
```


```python
# @title Make sure to set up set up your API keys correctly
from set_env import set_env
_ = set_env("ANTHROPIC_API_KEY")
_ = set_env("WANDB_API_KEY")
```

In this example, we'll create a [Weave Model](https://wandb.github.io/weave/guides/core-types/models) which is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates.
In this model, we will include our predict function where the Anthropic API will be called.

Once you run this code you will receive a link to the Weave project page


```python
import weave
import asyncio
from anthropic import AsyncAnthropic

# Weave model / predict function
class sentiment_analysis_model(weave.Model):
    model_name: str
    system_prompt: str
    temperature: int

    @weave.op()
    async def predict(self, text_block: str) -> dict:
        client =AsyncAnthropic()

        response = await client.messages.create(
            max_tokens=1024,
            model=self.model_name,
            system=self.system_prompt,
            messages=[
                {   "role": "user",
                    "content":[
                        {
                            "type": "text",
                            "text": text_block
                        }
                        ]
                 }
            ]
        )
        result = response.content[0].text
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return parsed


weave.init('sentiment_analysis-example')
# create our LLM model with a system prompt
model = sentiment_analysis_model(name="claude-3-sonnet",
                      model_name="claude-3-5-sonnet-20240620",
                      system_prompt="You are a Sentiment Analysis classifier. You will be classifying text based on their sentiment. Your input will be a block of text. You will answer with one the following rating option[\"positive\", \"negative\", \"neutral\"]. Your answer should be one word in json format: {classification}",
                      temperature=0
                      )
# for every block of text, anonymized first and then predict
for entry in pii_data:
  anonymized_entry = anonymize_my_text(entry["text"])
  (await model.predict(anonymized_entry))

```

# Method 1B: Replace PII data with fake data

Instead of redacting text, we can anonymize it by swapping PII (like names and phone numbers) with fake data generated using the [Faker](https://faker.readthedocs.io/en/master/) Python library. For example:


```
"My name is Raphael and I like to fish. My phone number is 212-555-5555"
```
Will be:


```
"My name is Katherine Dixon and I like to fish. My phone number is 667.431.7379"

```

To effectively utilize Presidio, we must supply references to our custom operators. These operators will direct Presidio to the functions responsible for swapping PII with fake data.


```python
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, EngineResult, RecognizerResult
from faker import Faker


fake = Faker()

# Create faker functions (note that it has to receive a value)
def fake_name(x):
    return fake.name()

def fake_number(x):
    return fake.phone_number()


# Create custom operator for the PERSON and PHONE_NUMBER" entities
operators = {
    "PERSON": OperatorConfig("custom", {"lambda": fake_name}),
    "PHONE_NUMBER": OperatorConfig("custom", {"lambda": fake_number}),
             }


text_to_anonymize = "My name is Raphael and I like to fish. My phone number is 212-555-5555"

# Analyzer output
analyzer_results = analyzer.analyze(text=text_to_anonymize,
                           entities=["PHONE_NUMBER", "PERSON"],
                           language='en')


anonymizer = AnonymizerEngine()

# do not forget to pass the operators from above to the anonymizer
anonymized_results = anonymizer.anonymize(
    text=text_to_anonymize, analyzer_results=analyzer_results, operators=operators
)

print(anonymized_results.text)
```

Let's consolidate our code into a single class and expand the list of entities to include the additional ones we identified earlier.


```python
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, EngineResult, RecognizerResult
from faker import Faker
import weave
import asyncio
from anthropic import AsyncAnthropic

# Let's build a custom class for generating fake data that will extend Faker
class my_faker(Faker):

  # Create faker functions (note that it has to receive a value)
  def fake_address(x):
    return fake.address()

  def fake_ssn(x):
    return fake.ssn()

  def fake_name(x):
    return fake.name()

  def fake_number(x):
    return fake.phone_number()

  def fake_email(x):
    return fake.email()

  # Create custom operators for the entities
  operators = {
    "PERSON": OperatorConfig("custom", {"lambda": fake_name}),
    "PHONE_NUMBER": OperatorConfig("custom", {"lambda": fake_number}),
    "EMAIL_ADDRESS": OperatorConfig("custom", {"lambda": fake_email}),
    "LOCATION": OperatorConfig("custom", {"lambda": fake_address}),
    "US_SSN":OperatorConfig("custom", {"lambda": fake_ssn})
             }

  def anonymize_my_text(self, text):
    anonymizer = AnonymizerEngine()
    analyzer_results = analyzer.analyze(text=text,
                           entities=["PHONE_NUMBER", "PERSON", "LOCATION", "EMAIL_ADDRESS", "US_SSN"],
                           language='en')
    anonymized_results = anonymizer.anonymize(text=text,
                            analyzer_results=analyzer_results, operators=self.operators)
    return anonymized_results.text


# Weave model / predict function
class sentiment_analysis_model(weave.Model):
    model_name: str
    system_prompt: str
    temperature: int

    @weave.op()
    async def predict(self, text_block: str) -> dict:
        client = AsyncAnthropic()

        response = await client.messages.create(
            max_tokens=1024,
            model=self.model_name,
            system=self.system_prompt,
            messages=[
                {   "role": "user",
                    "content":[
                        {
                            "type": "text",
                            "text": text_block
                        }
                        ]
                 }
            ]
        )
        result = response.content[0].text
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return parsed


### Start our fun work here ###
weave.init('sentiment_analysis-example')
# create our LLM model with the system prompt
model = sentiment_analysis_model(name="claude-3-sonnet",
                      model_name="claude-3-5-sonnet-20240620",
                      system_prompt="You are a Sentiment Analysis classifier. You will be classifying text based on their sentiment. Your input will be a block of text. You will answer with one the following rating option[\"positive\", \"negative\", \"neutral\"]. Your answer should one word in json format dict where the key is classification.",
                      temperature=0
                      )
faker = my_faker()
for entry in pii_data:
  anonymized_entry = faker.anonymize_my_text(entry["text"])
  (await model.predict(anonymized_entry))
```

*Optional Step*: For data traceability, add a hashing function after the anonymization process. This hash can be used to link the anonymized data back to its original form.

***Happy tracing!***
