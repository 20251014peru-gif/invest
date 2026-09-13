import {legacyDestination} from './research-routing.mjs';
const root=new URL('../',import.meta.url);
location.replace(new URL(legacyDestination(location.pathname,location.hash,location.search),root));
