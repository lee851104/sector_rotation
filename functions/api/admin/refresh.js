import {handleRefresh} from '../../_lib/handlers.js';
export const onRequest=context=>handleRefresh(context.request,context.env);
