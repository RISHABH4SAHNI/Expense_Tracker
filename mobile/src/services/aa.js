/**
 * Account Aggregator Service - Legacy Entry Point
 * 
 * This file maintains backward compatibility.
 * The actual AA integration has been moved to src/integrations/aa/
 */

export { aaService as default } from '../integrations/aa';
export * from '../integrations/aa';