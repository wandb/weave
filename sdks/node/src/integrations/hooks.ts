import {instrumentOpenAI} from '../integrations/openai';
import {instrumentAnthropic} from './anthropic';
instrumentOpenAI();
instrumentAnthropic();
