import weave
import asyncio
from weave.weaveflow import Model, Evaluation, Dataset
import json
from openai import OpenAI

def do_jack_extract():
    # We create a model class with one predict function. 
    # All inputs, predictions and parameters are automatically captured for easy inspection.
    @weave.type()
    class ExtractFinancialDetailsModel(Model):
        system_message: str
        model_name: str = "gpt-3.5-turbo-1106"

        @weave.op()
        async def predict(self, article: str) -> dict:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_message
                    },
                    {
                        "role": "user",
                        "content": article
                    }
                ],
                temperature=0.7,
                response_format={ "type": "json_object" }
            )
            extracted = response.choices[0].message.content
            return json.loads(extracted)

    # We call init to begin capturing data in the project, intro-example.
    weave.init('bodcleanrun')

    # We create our model with our system prompt.
    model = ExtractFinancialDetailsModel("You will be provided with financial news and your task is to parse it one JSON dictionary with company ticker, company name, document sentiment, and summary as keys. The summary should be a two sentance summary of the news.")

    # CNBC News Articles
    articles = ["Novo Nordisk and Eli Lilly rival soars 32 percent after promising weight loss drug results Shares of Denmarks Zealand Pharma shot 32 percent higher in morning trade, after results showed success in its liver disease treatment survodutide, which is also on trial as a drug to treat obesity. The trial “tells us that the 6mg dose is safe, which is the top dose used in the ongoing [Phase 3] obesity trial too,” one analyst said in a note. The results come amid feverish investor interest in drugs that can be used for weight loss.",
    "Berkshire shares jump after big profit gain as Buffetts conglomerate nears $1 trillion valuation Berkshire Hathaway shares rose on Monday after Warren Buffetts conglomerate posted strong earnings for the fourth quarter over the weekend. Berkshires Class A and B shares jumped more than 1.5%, each. Class A shares are higher by more than 17% this year, while Class B have gained more than 18%. Berkshire was last valued at $930.1 billion, up from $905.5 billion where it closed on Friday, according to FactSet. Berkshire on Saturday posted fourth-quarter operating earnings of $8.481 billion, about 28 percent higher than the $6.625 billion from the year-ago period, driven by big gains in its insurance business. Operating earnings refers to profits from businesses across insurance, railroads and utilities. Meanwhile, Berkshires cash levels also swelled to record levels. The conglomerate held $167.6 billion in cash in the fourth quarter, surpassing the $157.2 billion record the conglomerate held in the prior quarter.",
    "Highmark Health says its combining tech from Google and Epic to give doctors easier access to information Highmark Health announced it is integrating technology from Google Cloud and the health-care software company Epic Systems. The integration aims to make it easier for both payers and providers to access key information they need, even if its stored across multiple points and formats, the company said. Highmark is the parent company of a health plan with 7 million members, a provider network of 14 hospitals and other entities",
    "Rivian and Lucid shares plunge after weak EV earnings reports Shares of electric vehicle makers Rivian and Lucid fell Thursday after the companies reported stagnant production in their fourth-quarter earnings after the bell Wednesday. Rivian shares sank about 25 percent, and Lucids stock dropped around 17 percent. Rivian forecast it will make 57,000 vehicles in 2024, slightly less than the 57,232 vehicles it produced in 2023. Lucid said it expects to make 9,000 vehicles in 2024, more than the 8,428 vehicles it made in 2023.",
    "Mauritius blocks Norwegian cruise ship over fears of a potential cholera outbreak Local authorities on Sunday denied permission for the Norwegian Dawn ship, which has 2,184 passengers and 1,026 crew on board, to access the Mauritius capital of Port Louis, citing “potential health risks.” The Mauritius Ports Authority said Sunday that samples were taken from at least 15 passengers on board the cruise ship. A spokesperson for the U.S.-headquartered Norwegian Cruise Line Holdings said Sunday that 'a small number of guests experienced mild symptoms of a stomach-related illness' during Norwegian Dawns South Africa voyage.",
    "Intuitive Machines lands on the moon in historic first for a U.S. company Intuitive Machines Nova-C cargo lander, named Odysseus after the mythological Greek hero, is the first U.S. spacecraft to soft land on the lunar surface since 1972. Intuitive Machines is the first company to pull off a moon landing — government agencies have carried out all previously successful missions. The companys stock surged in extended trading Thursday, after falling 11 percent in regular trading.", 
    "Lunar landing photos: Intuitive Machines Odysseus sends back first images from the moon Intuitive Machines cargo moon lander Odysseus returned its first images from the surface. Company executives believe the lander caught its landing gear sideways in the moons surface while touching down and tipped over. Despite resting on its side, the companys historic IM-1 mission is still operating on the moon."
    ]

    labels = [
        {'company_name': 'Zealand Pharma', 'company_ticker': '0NZU-GB', 'document_sentiment': 'Positive'},
        {'company_name': 'Berkshire Hathaway', 'company_ticker': 'BRK', 'document_sentiment': 'Positive'},
        {'company_name': 'Highmark Health', 'company_ticker': 'N/A', 'document_sentiment': 'Positive'},
        {'company_name': ["Rivian","Lucid"], 'company_ticker': ["RIVN","LCID"], 'document_sentiment': 'Negative'},
        {'company_name': 'Norwegian Cruise Line Holdings', 'company_ticker': 'NCLH', 'document_sentiment': 'Negative'},
        {'company_name': 'Intuitive Machines', 'company_ticker': 'LUNR', 'document_sentiment': 'Positive'},
        {'company_name': 'Intuitive Machines', 'company_ticker': 'LUNR', 'document_sentiment': 'Positive'}
    ]

    # Create the evaluation dataset
    dataset = Dataset([
        {'id': '0', 'article': articles[0], 'extracted': labels[0]},
        {'id': '1', 'article': articles[1], 'extracted': labels[1]},
        {'id': '2', 'article': articles[2], 'extracted': labels[2]},
        {'id': '3', 'article': articles[3], 'extracted': labels[3]},
        {'id': '4', 'article': articles[4], 'extracted': labels[4]},
        {'id': '5', 'article': articles[5], 'extracted': labels[5]},
        {'id': '6', 'article': articles[6], 'extracted': labels[6]}
    ])
    dataset_ref = weave.publish(dataset, 'financial-articles')


    #define the hallucination model
    @weave.type()
    class DetermineHallucinationModel(Model):
        system_message: str
        model_name: str = "gpt-3.5-turbo-1106"

        @weave.op()
        def predict(self, text_to_analyze: str) -> dict:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_message
                    },
                    {
                        "role": "user",
                        "content": text_to_analyze
                    }
                ],
                temperature=0.7,
                response_format={ "type": "json_object" }
            )
            extracted = response.choices[0].message.content
            return json.loads(extracted)


    # We define four scoring functions to compare our model predictions with a ground truth label.
    @weave.op()
    def name_score(example: dict, prediction: dict) -> dict:
        # example is a row from the Dataset, prediction is the output of predict function
        return {'correct': example['extracted']['company_name'] == prediction['company_name']}

    @weave.op()
    def ticker_score(example: dict, prediction: dict) -> dict:
        return {'correct': example['extracted']['company_ticker'] == prediction['company_ticker']}

    @weave.op()
    def sentiment_score(example: dict, prediction: dict) -> dict:
        return {'correct': example['extracted']['document_sentiment'].lower() == prediction['document_sentiment'].lower()}

    @weave.op()
    def hallucination_score(example: dict, prediction: dict) -> dict:
        hallucination_calculation_model = DetermineHallucinationModel("You are in charge of determining if the text submitted is the result of LLM hallucination or not. Your task is to respond with a JSON dictionary including a single hallucanation score. The hallucination score should be a float from 0 to 100, where 100 is more likely and 0 is less likely that the text is hallucination or not.")
        return hallucination_calculation_model.predict(prediction['summary'])

    @weave.op()
    def example_to_model_input(example: dict) -> str:
        # example is a row from the Dataset, the output of this function should be the input to model.predict.
        return example["article"]

    # Finally, we run an evaluation of this model. 
    # This will generate a prediction for each input example, and then score it with each scoring function.
    evaluation = Evaluation(
        dataset, scores=[name_score, ticker_score, sentiment_score, hallucination_score], example_to_model_input=example_to_model_input
    )

    for i in range(0,10):
        print(asyncio.run(evaluation.evaluate(model)))


    @weave.op()
    def docs_to_embeddings(docs: list) -> list:
        from openai import OpenAI
        # Initialize the OpenAI API (Assuming you've set your API key in the environment)
        openai = OpenAI()

        # Convert documents to embeddings
        document_embeddings = []
        for doc in docs:
            response = openai.embeddings.create(input=doc, model="text-embedding-ada-002").data[0].embedding
            document_embeddings.append(response)
        
        return document_embeddings

    @weave.op()
    def get_most_relevant_document(query, docs, document_embeddings):
        from openai import OpenAI
        import numpy as np

        # Initialize the OpenAI API (Assuming you've set your API key in the environment)
        openai = OpenAI()    

        # Convert query to embedding
        query_embedding = openai.embeddings.create(input=query, model="text-embedding-ada-002").data[0].embedding
        
        # Compute cosine similarity
        similarities = [np.dot(query_embedding, doc_emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb)) for doc_emb in document_embeddings]
        
        # Get the index of the most similar document
        most_relevant_doc_index = np.argmax(similarities)
        
        return docs[most_relevant_doc_index]

    #define the Morgan Stanley Research RAG Model
    @weave.type()
    class MSResearchRAGModel(Model):
        system_message: str
        model_name: str = "gpt-3.5-turbo-1106"

        @weave.op()
        def predict(self, question: str, docs: list, add_context: bool) -> dict:
            from openai import OpenAI
            RAG_Context = ""
            # Retrieve the embeddings artifact
            embeddings = weave.ref('MSRAG_Embeddings').get()

            if add_context:
                # Using OpenAI Embeddings, get the relevant document for context
                RAG_Context = get_most_relevant_document(question, docs, embeddings)

            client = OpenAI()
            query = f"""Use the following information to answer the subsequent question. If the answer cannot be found, write "I don't know."
                        
                    Context from Morgan Stanley Research:
                    \"\"\"
                    {RAG_Context}
                    \"\"\"
                        
                    Question: {question}"""
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_message
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=0.7,
                response_format={ "type": "text" }
            )
            extracted = response.choices[0].message.content
            return extracted

    model = MSResearchRAGModel("You are an expert in finance and answer questions related to finance, financial services, and financial markets. When responding based on provided information, be sure to cite the source.")

    contexts = [f"""Morgan Stanley has moved in new market managers on the East and West Coasts as part of changes that sent some of other management veterans into new roles, according to two sources.

    On the West Coast, Ken Sullivan, a 37-year-industry veteran who came to Morgan Stanley five years ago from RBC Wealth Management, has assumed an expanded role as market executive for a consolidated Beverly Hills and Los Angeles market, according to a source.

    Meanwhile, Greg Laetsch, a 44-year industry veteran who had been the complex manager in Los Angeles for the last 15 years, has moved to a non-producing senior advisor role to the LA market for Morgan Stanley,  according to the same source. 

    On the East Coast, Morgan Stanley hired Nikolas Totaro, a 19-year industry veteran, from Merrill Lynch, where he had worked for 14 years and had been most recently a market executive in Greenwich, Connecticut. Totaro will be a market manager reporting to John Palazzetti in the Midtown Wealth Management Center in Manhattan, according to the same source. 

    Totaro is replacing Bill DeMatteo, a 21-year industry veteran who spent the last 14 years at Morgan Stanley, and who has returned to full-time production. DeMatteo has joined the Continuum Group at Morgan Stanley, which Barron’s ranked 20th among on its 2022 Top 100 Private Wealth Management Teams and listed as managing $7.2 billion in client assets.

    “His extensive 17 years of management experience at Morgan Stanley will be instrumental in shaping our approach to wealth management, fostering client relationships, and steering the team towards sustained growth and success,” Scott Siegel, leader of the Continuum Group, wrote on LinkedIn. 

    Totaro and Laestch did not respond immediately to requests for comments sent through LinkedIn. Sullivan did not respond immediately to an emailed request. Both Morgan Stanley and Merrill spokespersons declined to comment about the changes. 

    Totaro’s former Southern Connecticut market at Merrill included over 325 advisors and support staff across six offices in Greenwich, Stamford, Darien, Westport, Fairfield, and New Canaan, according to his LinkedIn profile. 

    Separately, a former Raymond James Financial divisional director has joined Janney Montgomery Scott in Ponte Vedra Beach, Florida. Tom M. Galvin, who has spent the last 25 years with Raymond James, joins Janney as a complex director, according to an announcement. 

    Galvin had most recently worked as a divisional director for Raymond James & Associates’ Southern Division. The firm consolidated the territory as part of a reorganization that took effect December 1. Galvin’s registration with Raymond James ended November 8, according to BrokerCheck. 

    During his career, Galvin has held a range of branch and complex management roles in the North Atlantic and along the East Coast, according to his LinkedIn profile. 

    “We’re looking forward to his experience and strong industry relationships as we continue to expand our team and geographic footprint,” stated Janney’s Florida Regional Director Frank Amigo, who joined from Raymond James in 2017. 

    Galvin started his career in 1995 with RBC predecessor firm J. B. Hanauer & Co. and joined Raymond James two years later, according to BrokerCheck. He did not immediately respond to a request for comment sent through social media.""",
                "",
                f"""Don’t Count on a March Rate Cut
    Inflation will be stickier than expected, delaying the start of long-awaited interest rate cuts.
    Investors expecting a rate cut in March may be disappointed.
    Six-month core consumer price inflation is likely to increase in the first quarter, prompting the Fed to watch and wait.
    Unless there is an unexpectedly sharp economic downturn or weakening in the labor market, rate cuts are more likely to begin in June.
    
    Investors betting that the U.S. Federal Reserve will begin trimming interest rates in the first quarter of 2024 may be in for a disappointment.

    After the Fed’s December meeting, market expectations for a March rate cut jumped to surprising heights. Markets are currently putting a 75% chance, approximately, on rate cuts beginning in March. However, Morgan Stanley Research forecasts indicate that cuts are unlikely to come before June.

    Central bank policymakers have likewise pushed back on investors’ expectations. As Federal Reserve Chairman Jerome Powell said in December 2023, when it comes to inflation, “No one is declaring victory. That would be premature.”1

    Here’s why we still expect that rates are likely to hold steady until the middle of 2024.

    Inflation Outlook
    A renewed uptick in core consumer prices is likely in the first quarter, as prices for services remain elevated, led by healthcare, housing and car insurance. Additionally, in monitoring inflation, the Fed will be watching the six-month average—which means that weaker inflation numbers from summer 2023 will drop out of the comparison window. Although annual inflation rates should continue to decline, the six-month gauge could nudge higher, to 2.4% in January and 2.69% in February.

    Labor markets have also proven resilient, giving Fed policymakers room to watch and wait.

    Data-Driven Expectations
    Data is critical to the Fed’s decisions and Morgan Stanley’s forecasts, and both could change as new information emerges. At the March policy meeting, the Fed will have only data from January and February in hand, which likely won’t provide enough information for the central bank to be ready to announce a rate cut. The Fed is likely to hold rates steady in March unless nonfarm payrolls add fewer than 50,000 jobs in February and core prices gain less than 0.2% month-over-month. However, unexpected swings in employment and consumer prices, or a marked change in financial conditions or labor force participation, could trigger a cut earlier than we anticipate.

    There are scenarios in which the Fed could cut rates before June, including: a pronounced deterioration in credit conditions, signs of a sharp economic downturn, or slower-than-expected job growth coupled with weak inflation. Weaker inflation and payrolls could bolster the chances of a May rate cut especially.

    When trying to assess timing, statements from Fed insiders are good indicators because they tend to communicate premeditated changes in policy well in advance. If the Fed plans to hold rates steady in March, they might emphasize patience, or talk about inflation remaining elevated. If they’re considering a cut, their language will shift, and they may begin to say that a change in policy may be appropriate “in coming meetings,” “in coming months” or even “soon.” But a long heads up is not guaranteed.
    https://www.morganstanley.com/ideas/fed-rate-cuts-2024
    """,
    f"""What Global Turmoil Could Mean for Investors
    Weighing the investment impacts of global conflict and geopolitical tensions to international trade, oil prices and China equities.
    Morgan Stanley Research expects cargo shipping to remain robust despite Red Sea disruption.
    Crude oil shipments and oil prices should see limited negative impact from regional conflict.
    Long-term trends could bring growth in Japan and India.
    In a multipolar world, competition for global power is increasingly leading countries to protect their military and economic interests by erecting new barriers to cross-border commerce in key industries such as technology and renewable energy. As geopolitics and national security are to a growing degree driving how goods flow and where big capital investments are made, it’s that much more crucial for investors to know how to pick through a dizzying amount of information and focus on what’s relevant. But it’s hard to do with a seemingly endless series of alerts lighting up your phone.

    In particular, potential ripples from U.S.-China relations as well as U.S. military involvement in the Middle East could be important for investors. Morgan Stanley Research pared back the headlines and market noise to home in on three key takeaways.

    Gauging Red Sea Disruption
    Commercial cargo ships in the Red Sea handle about 12% of global trade. Attacks on these ships by Houthi militants, and ongoing U.S. military strikes to quell the disruption, have raised concerns that supply chains could see pandemic-type disruption—and a corresponding spike in inflation.

    However, my colleagues and I expect the flow of container ships to remain robust, even if that flow is redirected to avoid the Red Sea, which serves as an outlet for vessels coming out of the Suez Canal. Although there has been a recent 200% surge in freight rates, there have not been fundamental cost increases for shipping. Additionally, there’s currently a surplus of container ships. Lengthy reroutes around the Southern tip of Africa by carriers to avoid the conflict zone may cause delays, but they should have minimal impact to inflation in Europe. The risks to the U.S. retail sector should be similarly manageable.

    Resilience in Oil and the Countries That Produce it
    The Middle East is responsible for supplying and producing the majority of the world’s oil, so escalating conflict in the region naturally puts pressure on energy supply, as well the economic growth of relevant countries. However, the threat of weaker growth, higher inflation and erosion of support from allies offer these countries an incentive to contain the conflict. As a result, there’s unlikely to be negative impact to the debt of oil-producing countries in the region. Crude oil shipments should also see limited impacts, though oil prices could spike and European oil refiners, in particular, could face pressure if disruption in the Strait of Hormuz, which traffics about a fifth of oil supplies daily, accelerates.

    Opportunities in Asia Emerging in Japan and India 
    China has significant work to do to retool its economic engine away from property, infrastructure and debt, leading Morgan Stanley economists to predict gross-domestic product growth of 4.2% for 2024 (below the government’s 5% target), slowing to 1.7% from 2025 to 2027. As a result, China’s relatively low equity market valuation still faces challenges, including risks such as U.S. policy restricting future investment. But elsewhere in Asia—particularly in standouts Japan and India—positive long-term trends should drive markets higher. These include fiscal rebalancing, increased digitalization and increasing shifts of manufacturing and supply hubs in a multipolar world.

    For a deeper insights and analysis, ask your Morgan Stanley Representative or Financial Advisor for the full report, “Paying Attention to Global Tension.”
    https://www.morganstanley.com/ideas/geopolitical-risk-2024
    """,
    f"""What 'Edge AI' Means for Smartphones
    As generative artificial intelligence gets embedded in devices, consumers should see brand new features while smartphone manufacturers could see a sales lift.
    Advances in artificial intelligence are pushing computing from the cloud directly onto consumer devices, such as smartphones, notebooks, wearables, automobiles and drones.
    This trend is expected to drive smartphone sales during the next two years, reversing a slowdown that began in 2021.
    Consumers can expect new features, such as touch-free control of their phones, desktop-quality gaming and real-time photo retouching.
    As the adoption of generative artificial intelligence accelerates, more computing will be done in the hands of end users—literally. Increasingly, AI will be embedded in consumer devices such as smartphones, notebooks, wearables, automobiles and drones, creating new opportunities and challenges for the manufacturers of these devices.

    Generative AI’s phenomenal capabilities are power-intensive. So far, the processing needed to run sophisticated, mainstream generative AI models can only take place in the cloud. While the cloud will remain the foundation of AI infrastructure, more AI applications, functions and services require faster or more secure computing closer to the consumer. “That’s driving the need for AI algorithms that run locally on the devices rather than on a centralized cloud—or what’s known as the AI at the Edge,” says Ed Stanley, Morgan Stanley’s Head of Thematic Research in London.

    By 2025, Edge AI will be responsible for half of all enterprise data created, according to an estimate by technology market researcher Gartner Inc. While there are many hurdles to reaching commercial viability, the opportunity to tap into 30 billion devices could reduce cost, increase personalization, and improve security and privacy. In addition, faster algorithms on the Edge can reduce latency (i.e., the lag in an app’s response time as it communicates with the cloud).

    “If 2023 was the year of generative AI, 2024 could be the year the technology moves to the Edge,” says Stanley. “We think this trend will pick up steam in 2024, and along with it, opportunities for hardware makers and component suppliers that can help put AI directly into consumers' hands.”

    New Smartphones Lead the Charge
    Smartphones currently on the market rely on traditional processors and cloud-based computing, and the only AI-enabled programs are features like face recognition, voice assist and low-light photography. Device sales have slowed in recent years, and many investors expect that smartphones will follow the trajectory of personal computers, with multi-year downturns as consumers hold onto their devices for longer due to lack of new features, sensitivity to pricing and other factors.

    But thanks in part to Edge AI, Morgan Stanley analysts think the smartphone market is poised for an upswing and predict that shipments, which have slowed since 2021, will rise by 3.9% this year and 4.4% next year.

    “Given the size of the smartphone market and consumers’ familiarity with them, it makes sense that they will lead the way in bringing AI to the Edge,” says Morgan Stanley’s U.S. Hardware analyst Erik Woodring. “This year should bring a rollout of generative AI-enabled operating systems, as well as next-generation devices and voice assistants that could spur a cycle of smartphone upgrades.”

    However, the move to the Edge will require new smartphone capabilities, especially to improve battery life, power consumption, processing speed and memory. Manufacturers with the strongest brands and balance sheets are best positioned to take the lead in the hardware arms race.

    Killer Apps
    In addition to hardware, AI itself continues to evolve. New generations of AI models are designed be more flexible and adaptable for a wide range of uses, including Edge devices. Other beneficiaries include smartphone memory players, integrated circuit makers and camera parts suppliers that support new AI applications.

    What can you expect from your phone in the next year?

    “Always-sensing cameras” that automatically activate or lock the screen by detecting if the user is looking at it without the need to touch the screen. This feature could also automatically launch applications such as online payment and food ordering by detecting bar codes.
    
    Gesture controls for when the user is unable to hold their devices, such as while cooking or exercising.
    
    Desktop-quality gaming experiences that offer ultra-realistic graphics with cinematic detail, all with smoother interactions and blazing-fast response times.
    
    Professional-level photography in which image processors enhance photos and video in real time by recognizing each element in a frame—faces, hair, glasses, objects—and fine tune each, eliminating the need for retouching later.
    
    Smarter voice assistance that is more responsive and tuned the user’s voice and speech patterns, and can launch or suggest apps based on auditory clues.
    
    “With Edge AI becoming part of everyday life, we see significant opportunities ahead as new hardware provides a platform for developers to create ground-breaking generative AI apps, which could trigger a new hardware product cycle that liftsservices sales,” says Woodring.

    For deeper insights and analysis, ask your Morgan Stanley Representative or Financial Advisor for the full reports, “Tech Diffusion: Edge AI—Growing Impetus” (Nov. 7, 2023), “Edging Into a Smartphone Upcycle” (Nov. 9, 2023) and “Edge AI: Product Releases on Track, But Where Are Killer Apps?”
    https://www.morganstanley.com/ideas/edge-ai-devices-diffusion"""]

    questions = ["Can you summarize the latest changes to Morgan Stanley market managers?",
                "When will the fed raise rates?",
                "What are the top market risks?",
                "How will AI impact the smartphone market?"
                ]


    # Calculate the document embeddings and store in weave
    document_embeddings = docs_to_embeddings(contexts)
    embeddings_ref = weave.publish(document_embeddings, 'MSRAG_Embeddings')


    for i in range (0,len(questions)):
        # Not using OpenAI Embeddings
        print(model.predict(questions[i], contexts, True))

    print(model.predict(questions[1], contexts, False))
