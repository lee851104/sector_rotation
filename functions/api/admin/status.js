import {handleStatus} from '../../_lib/handlers.js';
export const onRequestGet=context=>handleStatus(context.request,context.env);
