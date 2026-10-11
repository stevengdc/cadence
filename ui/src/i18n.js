import en from './locales/en.json';
import pt from './locales/pt.json';
export const language=localStorage.getItem('cadence.language')==='pt'?'pt':'en';
const messages=language==='pt'?pt:en;
export function t(text){if(typeof text!=='string')return text;if(messages[text])return messages[text];const key=text.trim();return messages[key]?text.replace(key,messages[key]):text}
export function setLanguage(value){localStorage.setItem('cadence.language',value==='pt'?'pt':'en');location.reload()}
document.documentElement.lang=language;
