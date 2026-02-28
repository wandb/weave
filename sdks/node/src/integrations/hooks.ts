import {instrumentOpenAI} from '../integrations/openai';
import {instrumentAnthropic} from './anthropic';
import {instrumentOpenAIAgent} from './openai.agent';
instrumentOpenAI();
instrumentAnthropic();
instrumentOpenAIAgent();
