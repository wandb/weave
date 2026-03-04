import {instrumentOpenAI} from '../integrations/openai';
import {instrumentAnthropic} from './anthropic';
import {instrumentGoogleGenAI} from './googleGenAI';
import {instrumentOpenAIAgent} from './openai.agent';
instrumentOpenAI();
instrumentAnthropic();
instrumentGoogleGenAI();
instrumentOpenAIAgent();
