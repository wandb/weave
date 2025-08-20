require('dotenv').config();

import { OpenAI } from 'openai';
import * as weave from 'weave';
import { writeFileSync, readFileSync } from 'fs';
import { Writer } from 'wav';

/**
 * # Weave with OpenAI Audio Integration
 * 
 * You can use W&B Weave with OpenAI's Audio API to:
 * - Track and debug audio generation inputs, outputs, and traces
 * - Log audio files, transcripts, and metadata automatically
 * - Maintain conversation history with audio responses
 * - Monitor API costs and usage across audio generations
 * 
 * For more information, see the [Weave documentation](/).
 */

/**
 * ## 🔧 Setup & Initialization
 */
async function initializeWeaveProject() {
    await weave.init('openai-audio-chat');
}

function initializeOpenAIClient() {
    return weave.wrapOpenAI(new OpenAI({
        apiKey: process.env.OPENAI_API_KEY
    }));
}

/**
 * ## 📝 Type Definitions
 * Define the structure for audio responses and messages
 */
interface AudioResponse {
    audioData: ReturnType<typeof weave.weaveAudio>;
    transcript?: string;
    id?: string;
}

interface Message {
    role: "user" | "assistant";
    content?: string;
    audio?: {
        data: ReturnType<typeof weave.weaveAudio>;
        transcript?: string;
        id?: string | null;
    };
}

/**
 * ## Audio Generation Tracking
 * 
 * Weave automatically tracks all OpenAI audio calls, including:
 * - Audio files and transcripts
 * - Token usage and API costs
 * - Model configurations
 * - Request/response pairs
 * 
 * :::note
 * The audio feature requires the GPT-4 Audio Preview model. Make sure you have access
 * to this model in your OpenAI account.
 * :::
 */
const generateAudioResponse = weave.op(async function generateAudioResponse({
    userPrompt = "",
    previousMessages = [] as Message[]
}) {

    const client = initializeOpenAIClient();
    const messages = [
        ...previousMessages.map((msg: Message) => ({
            role: msg.role,
            content: msg.content || msg.audio?.transcript || null,
        })),
        {
            role: "user" as const,
            content: userPrompt
        }
    ];

    const response = await client.chat.completions.create({
        model: "gpt-4o-audio-preview",
        modalities: ["text", "audio"],
        audio: { 
            voice: "alloy", 
            format: "wav" 
        },
        messages,
        store: true,
    });

    const message = response.choices[0].message;
    
    // Check if the response contains audio data
    if (message.audio?.data) {
        const audioData = Buffer.from(message.audio.data, 'base64');
        return {
            audioData: weave.weaveAudio({data: audioData}),
            transcript: message.audio.transcript,
            id: message.audio.id
        } as AudioResponse;
    }
    
    // If no audio data, return the text content
    return {
        audioData: weave.weaveAudio({data: Buffer.from(message.content || '', 'utf-8')}),
        transcript: message.content
    } as AudioResponse;
});

/**
 * ## 🚀 Example Usage
 * 
 * Demonstrate a multi-turn conversation with audio responses
 */
const weaveAudioExample = weave.op(async function AudioExample() {
    await initializeWeaveProject();
    
    // First message: Ask about golden retrievers
    const firstResponse = await generateAudioResponse({
        userPrompt: "Is a golden retriever a good family dog?",
        previousMessages: [{
            role: "system",
            content: "You are an expert on dogs especially golden retrievers."
        }]
    });
    
    // Follow-up question using conversation history
    const secondResponse = await generateAudioResponse({
        userPrompt: "Why do you say they are loyal?",
        previousMessages: [
            {
                role: "system",
                content: "You are an expert on dogs especially golden retrievers."
            },
            {
                role: "user",
                content: "Is a golden retriever a good family dog?"
            },
            {
                role: "assistant",
                audio: {
                    data: firstResponse.audioData,
                    transcript: firstResponse.transcript,
                    id: firstResponse.id
                }
            }
        ]
    });
}); 

async function main() {
    await weaveAudioExample();
}

// Execute the main function
if (require.main === module) {
    main().catch(error => {
        console.error('Error running audio example:', error);
        process.exit(1);
    });
}

