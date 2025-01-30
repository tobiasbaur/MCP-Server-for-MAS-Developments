#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
    CallToolRequestSchema,
    ErrorCode,
    ListResourcesRequestSchema,
    ListResourceTemplatesRequestSchema,
    ListToolsRequestSchema,
    McpError,
    ReadResourceRequestSchema
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import https from 'https';
import dotenv from 'dotenv';    
import net from 'net';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import os from 'os';
import crypto from 'crypto';
import moment from 'moment'; // Optional: Entfernen, wenn nicht benötigt
// Entfernen Sie die folgende Zeile, wenn Winston bereits in logger.js importiert und verwendet wird
import winston from 'winston';
import { messages } from './pgpt-messages.js';
import { logEvent } from './logger.js'; // Importieren der logEvent Funktion
import figlet from 'figlet';
import chalk from 'chalk';
import { promisify } from 'util';
import express from 'express';
import { createServer as createHttpServer } from 'http';
import { Server as SocketIoServer } from 'socket.io';
import chokidar from 'chokidar';
import stripAnsi from 'strip-ansi';



// Promisifizieren von figlet.text für die Verwendung mit async/await
const figletAsync = promisify(figlet.text);

dotenv.config({ path: './pgpt.env' }); // Geben Sie explizit den Pfad zur Datei an

// JSON-Datei laden
// `__dirname`-Ersatz für ES-Module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// JSON-Dateipfad relativ zum Skript
const envFilePath = path.resolve(__dirname, '../pgpt.env.json');
let envConfig;

try {
    envConfig = JSON.parse(fs.readFileSync(envFilePath, 'utf-8'));
} catch (error) {
    logEvent('system', 'N/A', 'Env Load Err', error.message, 'error');
    process.exit(1);
}
// Helper-Funktionen
function getEnvVar(key, nestedPath = null, fallback = null) {
    // Prüfen, ob ein verschachtelter Pfad angegeben ist
    if (nestedPath) {
        const value = nestedPath.reduce((acc, part) => acc && acc[part], envConfig);
        if (value === undefined || value === null) {
            if (fallback !== null) return fallback;
            logEvent(
                'system',
                'N/A',
                'Missing Config',
                t.missingConfigError.replace('${key}', key),
                'error'
            );
            process.exit(1);
        }
        return value;
    }
    // Direkter Zugriff
    if (envConfig[key] === undefined || envConfig[key] === null) {
        if (fallback !== null) return fallback;
        logEvent('system', 'N/A', 'Missing Config', `Missing .json configuration variable: ${key}`, 'error');
        process.exit(1);
    }
    return envConfig[key];
}

// Nachrichten basierend auf Sprache
let lang = getEnvVar('LANGUAGE', ['Server_Config', 'LANGUAGE'], 'en').toLowerCase();
if (!(lang in messages)) {
    logEvent('system', 'N/A', 'Lang Warning', 'Language "${lang}" is not supported. Fallback in English.', 'warn');
    lang = 'en';
}

const t = messages[lang];
/**
 * Funktion zum Anzeigen des Startheaders
 */
function displayStartHeader() {
    // Generiere ASCII-Art
    figlet.text('Fujitsu PGPT MCP-Server', {
        font: 'Slant', // Schriftart, kann angepasst werden
        horizontalLayout: 'default',
        verticalLayout: 'default',
        width: 80,
        whitespaceBreak: true
    }, function(err, data) {
        if (err) {
            logEvent('system', 'N/A', 'Logo Load Err', t.errorCreatingAsciiArt, 'error');
            console.dir(err);
            return;
        }
        // Farbige Ausgabe mit Chalk
        console.log(
            chalk.green.bold(data) + '\n' +
            chalk.blue(`${t.mcpVersion} 2.1.0\n`) +
            chalk.yellow(`${t.mcpPort} ${Port}\n`) +
            chalk.cyan(`${t.mcpStartTime} ${new Date().toLocaleString()}\n`) +
            chalk.magenta(`${t.mcpLicense} MIT`)
        );
    });
}

const privateApiUrl = getEnvVar('PRIVATE_GPT_API_URL', ['PGPT_Url', 'PRIVATE_GPT_API_URL']);
const requestedLang = getEnvVar('LANGUAGE', ['Server_Config', 'LANGUAGE'], 'en').toLowerCase();
const apiUrl = getEnvVar('API_URL', ['PGPT_Url', 'API_URL']);
const Port = getEnvVar('PORT', ['Server_Config', 'PORT'], '5000');
const restrictedGroups = getEnvVar('RESTRICTED_GROUPS', ['Restrictions', 'RESTRICTED_GROUPS'], 'false').toString();
const sslValidate = getEnvVar('SSL_VALIDATE', ['Server_Config', 'SSL_VALIDATE'], 'false').toString();
const PwEncryption = getEnvVar('PW_ENCRYPTION', ['Server_Config', 'PW_ENCRYPTION'], 'false') === 'true';
const AllowKeygen = getEnvVar('ALLOW_KEYGEN', ['Server_Config', 'ALLOW_KEYGEN'], 'false') === 'true';
const allowLogging = getEnvVar('ALLOW_LOGGING', ['Logging', 'ALLOW_LOGGING'], 'false').toString();
const LogIps = getEnvVar('LOG_IPs', ['Logging', 'LOG_IPs'], 'false').toString();
const anonymousMode = getEnvVar('ANONYMOUS_MODE', ['Logging', 'ANONYMOUS_MODE'], 'false').toString();


// Funktion zur Pfad-Expansion
function expandPath(filePath) {
    if (filePath.startsWith('~')) {
        return path.join(os.homedir(), filePath.slice(1));
    }
    return filePath;
}

// Load the public key
const publicKeyPath = expandPath(getEnvVar('PUBLIC_KEY', ['Server_Config', 'PUBLIC_KEY']));
const privateKeyPath = expandPath(getEnvVar('PRIVATE_KEY', ['Server_Config', 'PRIVATE_KEY']));

let publicKey;
let privateKey;

try {
    publicKey = fs.readFileSync(publicKeyPath, 'utf8');
    privateKey = fs.readFileSync(privateKeyPath, 'utf8');
    logEvent('system', 'N/A', 'Public Key', publicKey, 'info');
    logEvent('system', 'N/A', 'Private Key', privateKey, 'info');
} catch (error) {
    logEvent('system', 'N/A', t.fileReadErrorTitle, error.message, 'error');
    logEvent('system', 'N/A', 'File Path', error.path, 'error');
    process.exit(1); // Abbrechen, falls Schlüssel nicht geladen werden können
}

if (PwEncryption) {
    logEvent('system', 'N/A', 'PW Encryption', t.passwordEncEnabled, 'info');
} else {
    logEvent('system', 'N/A', 'PW Encryption', t.passwordEncDisabled, 'info');
}

function validateUrl(url, t) {
    if (!url.startsWith('https://')) {
        logEvent('system', 'N/A', 'URL Warning', t.apiUrlWarning, 'warn');
        url = url.replace(/^http:\/\//, 'https://');
    }
    url = url.replace(/([^:]\/)\/+/g, '$1'); // Doppelte Schrägstriche nach "://" entfernen
    if (!url.endsWith('/api/v1')) {
        logEvent('system', 'N/A', 'URL Warning V1', t.apiUrlWarningV1, 'warn');
        url = `${url.replace(/\/$/, '')}/api/v1`;
    }
    try {
        new URL(url);
    } catch {
        logEvent('system', 'N/A', 'URL Invalid', `${t.apiUrlInvalid} ${url}`, 'error');
        process.exit(1);
    }
    return url;
}

function validatePort(port, t) {
    const portNumber = parseInt(port, 10);
    if (isNaN(portNumber) || portNumber < 1 || portNumber > 65535) {
        logEvent('system', 'N/A', 'Port Invalid', t.portInvalid, 'error');
        process.exit(1);
    }
    return portNumber;
}

function validateBoolean(varName, value, t, useProxy = false) {
    if (useProxy && (varName === 'HEADER_ENCRYPTED')) {
        if (value !== 'true' && value !== 'false') {
            logEvent('system', 'N/A', 'Validation Err',
                t.validationError.replace('${var}', varName).replace('${value}', value), 'error');
            process.exit(1);
        }
        return value === 'true';
    }
    // Allgemeine Validierung
    if (value !== 'true' && value !== 'false') {
        logEvent('system', 'N/A', 'Validation Err',
            t.validationError.replace('${var}', varName).replace('${value}', value), 'error');
        process.exit(1);
    }
    return value === 'true';
}

/**
 * Decrypt a cryptographic string using the private key.
 * @param {string} encryptedData - The encrypted string in Base64 format.
 * @returns {string} - The decrypted password.
 */
function decryptPassword(encryptedData) {
    try {
        const decryptedPassword = crypto.privateDecrypt(
            {
                key: privateKey,
                padding: crypto.constants.RSA_PKCS1_PADDING, // Ensure consistent padding
            },
            Buffer.from(encryptedData, 'base64')
        ).toString('utf8');

        return decryptedPassword;
    } catch (error) {
        logEvent('system', 'N/A', t.decryptionError, error.message, 'error');
        throw new Error(t.decryptPwdError);
    }
}

// Function for encryption
function encryptWithPublicKey(data) {
    try {
        return crypto.publicEncrypt(
            {
                key: publicKey,
                padding: crypto.constants.RSA_PKCS1_PADDING, // Explicitly set padding
            },
            Buffer.from(data)
        ).toString('base64');
    } catch (err) {
        logEvent('system', 'N/A', t.encryptionError, err.message, 'error');
        throw new Error(t.encryptPwdError);
    }
}

/**
 * Encrypt a given password and return the encrypted key.
 * @param {string} password - The password to be encrypted.
 * @returns {string} - The encrypted password as a Base64 string.
 */
function getEncryptedKey(password) {
    try {
        return encryptWithPublicKey(password);
    } catch (err) {
        // Die Fehlerbehandlung wurde bereits in encryptWithPublicKey durchgeführt
        throw err;
    }
}

const enableLogin = getEnvVar('ENABLE_LOGIN', ['Functions', 'ENABLE_LOGIN'], false);
const enableLogout = getEnvVar('ENABLE_LOGOUT', ['Functions', 'ENABLE_LOGOUT'], false);
const enableChat = getEnvVar('ENABLE_CHAT', ['Functions', 'ENABLE_CHAT'], false);
const enableContinueChat = getEnvVar('ENABLE_CONTINUE_CHAT', ['Functions', 'ENABLE_CONTINUE_CHAT'], false);
const enableGetChatInfo = getEnvVar('ENABLE_GET_CHAT_INFO', ['Functions', 'ENABLE_GET_CHAT_INFO'], false);
const enableListGroups = getEnvVar('ENABLE_LIST_GROUPS', ['Functions', 'ENABLE_LIST_GROUPS'], false);
const enableStoreGroup = getEnvVar('ENABLE_STORE_GROUP', ['Functions', 'ENABLE_STORE_GROUP'], false);
const enableDeleteGroup = getEnvVar('ENABLE_DELETE_GROUP', ['Functions', 'ENABLE_DELETE_GROUP'], false);
const enableCreateSource = getEnvVar('ENABLE_CREATE_SOURCE', ['Functions', 'ENABLE_CREATE_SOURCE'], false);
const enableEditSource = getEnvVar('ENABLE_EDIT_SOURCE', ['Functions', 'ENABLE_EDIT_SOURCE'], false);
const enableDeleteSource = getEnvVar('ENABLE_DELETE_SOURCE', ['Functions', 'ENABLE_DELETE_SOURCE'], false);
const enableGetSource = getEnvVar('ENABLE_GET_SOURCE', ['Functions', 'ENABLE_GET_SOURCE'], false);
const enableListSources = getEnvVar('ENABLE_LIST_SOURCES', ['Functions', 'ENABLE_LIST_SOURCES'], false);
const enableStoreUser = getEnvVar('ENABLE_STORE_USER', ['Functions', 'ENABLE_STORE_USER'], false);
const enableEditUser = getEnvVar('ENABLE_EDIT_USER', ['Functions', 'ENABLE_EDIT_USER'], false);
const enableDeleteUser = getEnvVar('ENABLE_DELETE_USER', ['Functions', 'ENABLE_DELETE_USER'], false);

// Loggen der Server-Konfiguration
logEvent('system', 'N/A', 'Server Config', JSON.stringify(envConfig, null, 2), 'info');

logEvent('system', 'N/A', 'Private API URL', privateApiUrl, 'info');
logEvent('system', 'N/A', 'Public API URL', apiUrl, 'info');
logEvent('system', 'N/A', 'Port', Port, 'info');
logEvent('system', 'N/A', 'Language', requestedLang, 'info');
logEvent('system', 'N/A', 'SSL Validation', sslValidate, 'info');
logEvent('system', 'N/A', 'PW Encryption', PwEncryption ? t.encryptionEnabled : t.encryptionDisabled, 'info');
logEvent('system', 'N/A', 'Allow Keygen', AllowKeygen ? t.keygenEnabled : t.keygenDisabled, 'info');
logEvent('system', 'N/A', 'Private Key Path', privateKeyPath, 'info');
logEvent('system', 'N/A', 'Public Key Path', publicKeyPath, 'info');
logEvent('system', 'N/A', 'Restricted Groups', restrictedGroups, 'info');
logEvent('system', 'N/A', 'ALLOW_LOGGING', allowLogging, 'info');
logEvent('system', 'N/A', 'LOG_IPs', LogIps, 'info');
logEvent('system', 'N/A', 'ANONYMOUS_MODE', anonymousMode, 'info');

// Loggen der deaktivierten Funktionen
const allFunctions = [
  { name: 'Login', enabled: enableLogin },
  { name: 'Logout', enabled: enableLogout },
  { name: 'Chat', enabled: enableChat },
  { name: 'Continue Chat', enabled: enableContinueChat },
  { name: 'Get Chat Info', enabled: enableGetChatInfo },
  { name: 'List Groups', enabled: enableListGroups },
  { name: 'Store Group', enabled: enableStoreGroup },
  { name: 'Delete Group', enabled: enableDeleteGroup },
  { name: 'Create Source', enabled: enableCreateSource },
  { name: 'Edit Source', enabled: enableEditSource },
  { name: 'Delete Source', enabled: enableDeleteSource },
  { name: 'Get Source', enabled: enableGetSource },
  { name: 'List Sources', enabled: enableListSources },
  { name: 'Store User', enabled: enableStoreUser },
  { name: 'Edit User', enabled: enableEditUser },
  { name: 'Delete User', enabled: enableDeleteUser }
];

// Filtern, um nur deaktivierte (false) zu bekommen
const disabledFunctions = allFunctions.filter(f => !f.enabled);

// Loggen der deaktivierten Funktionen
if (disabledFunctions.length === 0) {
    logEvent(
      'system',
      'N/A',
      'All Funcs',
      t.allFunctionsEnabled,
      'info'
    );
} else {
    logEvent('system', 'N/A', 'Deact Funcs', t.deactivatedFunctions, 'warn');
    disabledFunctions.forEach(func => {
        logEvent('system', 'N/A', func.name, t.functionDisabled, 'warn');
    });
}


logEvent('system', 'N/A', 'API URL Valid', t.apiUrlValidated.replace('${url}', apiUrl), 'info');

// Debugging für RESTRICTED_GROUPS
logEvent(
    'system',
    'N/A',
    'Access RESTRICTED_GROUPS',
    t.accessRestrictedGroups.replace('${val}', envConfig.Restrictions?.RESTRICTED_GROUPS.toString()),
    'info'
);

// Zugriff und Validierung von RESTRICTED_GROUPS
const isRestrictedGroupsEnabled = validateBoolean(
    'RESTRICTED_GROUPS',
    restrictedGroups,
    t
);

logEvent('system', 'N/A', 'Restricted Groups', t.restrictedGroupsSuccess.replace('${status}', isRestrictedGroupsEnabled.toString()), 'info');


// Zugriff und Validierung von ALLOW_LOGGING
const isAllowLoggingEnabled = validateBoolean(
    'ALLOW_LOGGING',
    allowLogging,
    t
);
logEvent('system', 'N/A', 'allow Logging', t.AllowLoggingSuccess.replace('${status}', isAllowLoggingEnabled.toString()), 'info');

// Zugriff und Validierung von LOG_IPs
const isLogIpsEnabled = validateBoolean(
    'LOG_IPs',
    LogIps,
    t
);
logEvent('system', 'N/A', 'Log IPs', t.LogIpsSuccess.replace('${status}', isLogIpsEnabled.toString()), 'info');

// Zugriff und Validierung von ANONYMOUS_MODE
const isanonymousModeEnabled = validateBoolean(
    'ANONYMOUS_MODE',
    anonymousMode,
    t
);
logEvent('system', 'N/A', 'anonymous Mode', t.anonymousModeSuccess.replace('${status}', isanonymousModeEnabled.toString()), 'info');

function baseLogOptions() {
    return {
        AllowLoggingEnabled: isAllowLoggingEnabled,
        LogIps: isLogIpsEnabled,
        anonymousMode: isanonymousModeEnabled,
    };
}

// SSL-Validierung
const isSSLValidationEnabled = validateBoolean(
    'SSL_VALIDATE',
    getEnvVar('SSL_VALIDATE', ['Server_Config', 'SSL_VALIDATE'], 'false').toString(),
    t
);

const sslSymbol = isSSLValidationEnabled ? '✔️' : '⚠️';
logEvent('system', 'N/A', 'SSL Validation',
    t.sslValidationSet
        .replace('${symbol}', sslSymbol)
        .replace('${value}', String(isSSLValidationEnabled)),
    'info'
);

// Port validieren
const validatedPort = validatePort(Port, t);
logEvent('system', 'N/A', 'Port Validated', t.portValidated.replace('${port}', validatedPort), 'info');

// Einlesen der Proxy_Config-Parameter
const useProxy = validateBoolean(
    'USE_PROXY',
    getEnvVar('USE_PROXY', ['Proxy_Config', 'USE_PROXY'], 'false').toString(),
    t
);

const authHeaderEncrypted = useProxy ? validateBoolean(
    'HEADER_ENCRYPTED',
    getEnvVar('HEADER_ENCRYPTED', ['Proxy_Config', 'HEADER_ENCRYPTED'], 'false').toString(),
    t,
    useProxy
) : false;

const AccessHeader = useProxy ? getEnvVar('ACCESS_HEADER', ['Proxy_Config', 'ACCESS_HEADER'], null) : null;

// Verarbeiten des Proxy-Passworts
let ProxyAccessHeader;
if (authHeaderEncrypted) {
    try {
        ProxyAccessHeader = decryptPassword(AccessHeader);
    } catch (error) {
        logEvent('system', 'N/A', 'Proxy Decryption Error', error.message, 'error');
        process.exit(1);
    }
} else {
    ProxyAccessHeader = AccessHeader;
}

// Falls in der HAProxy-Konfiguration ein X-Custom-Header verlangt wird:
const customHeaderValue = ProxyAccessHeader;

// Optional: Überprüfen, ob alle erforderlichen Proxy-Daten vorhanden sind
if (useProxy && authHeaderEncrypted) {
    if (!ProxyAccessHeader) {
        logEvent('system', 'N/A', 'Proxy Auth Err', t.proxyAuthMissing, 'error');
        process.exit(1);
    }
}

// Ausgabe der Proxy-Konfiguration (mit maskiertem Passwort)
logEvent('system', 'N/A', 'Proxy Config', t.proxyUseProxy.replace('${val}', useProxy), 'info');
// logEvent('system', 'N/A', 'login', t.loginMissingCredentials, 'error');
// logEvent('system', 'N/A', 'continue_chat', t.missingChatParams, 'error');


// Beispiel: Tool-Überprüfung
function isToolEnabled(toolName) {
    const envKey = `ENABLE_${toolName.toUpperCase()}`;
    if (!(envKey in envConfig.Functions)) {
        logEvent(
            'system', 'N/A', 'Tool Warn', t.toolNotDefinedInConfig.replace('${toolName}', toolName), 'warn'
        );
        return false;
    }
    return envConfig.Functions[envKey] === true;
}

/* ################ Helper Functions ############################*/
// Helper-Funktion, um zu prüfen, ob ein Tool aktiviert ist, und eine Fehlermeldung zu generieren
function checkToolEnabled(toolName) {
    if (toolName === "keygen" && AllowKeygen) {
        return null;
    }

    if (!isToolEnabled(toolName)) {
        logEvent(
            'system', 'N/A', 'Tool Disabled', t.toolDisabledLog.replace('${toolName}', toolName), 'error'
        );
        return {
            status: 'error',
            message: messages[lang].toolDisabledError.replace('${toolName}', toolName),
        };
    }
    return null; // Tool ist aktiviert
}

function validateToken(token) {
    if (!token) {
        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'Token Valid', t.tokenMissingError, 'error');
        return {
            status: 'error',
            message: t.missingTokenError,
            statusCode: 401 // Optional für konsistenten HTTP-Status
        };
    }
    return null;
}

function getArguments(input) {
    if (input.arguments) {
        return input.arguments;
    } else if (input.params?.arguments) {
        return input.params.arguments;
    } else {
        if (!isanonymousModeEnabled) logEvent(
            'system', 'N/A', 'Invalid Args', t.invalidArgumentsError.replace('${args}', JSON.stringify(input)), 'error'
        );
        return {}; // Leeres Objekt als Fallback
    }
}

// Parameter zuordnen
const API_URL = apiUrl;
const PORT = Port;

// Server-Startkonfiguration ausgeben
const serverConfig = JSON.stringify({ API_URL, PORT }, null, 2); 
logEvent('system', 'N/A', 'Start Config', t.serverStartedLog, 'info');

// mit Konfiguration: ${serverConfig}

// Funktion zum Erstellen der Authorization-Header für Basic Auth
function createBasicAuthHeader(username, password) {
    const authString = Buffer.from(`${username}:${password}`).toString('base64');
    return `Basic ${authString}`;
}

/**
 * Zentrale Logging-Funktion
 * @param {string} clientIP - IP-Adresse des Clients
 * @param {number|string} clientPort - Port des Clients
 * @param {string} functionName - Name der aufgerufenen Funktion
 * @param {string} status - Status der Rückmeldung
 */
 const logger = winston.createLogger({
    level: 'info',
    format: winston.format.printf(({ level, message }) => message),
    transports: [
        new winston.transports.Console()
    ],
});

class TcpServerTransport {
    constructor(port) {
        this.port = port;
        this.server = null;
        this.clients = new Map(); // Map zur Speicherung der Clients
    }

    async start(onMessage) {
        return new Promise((resolve, reject) => {
            // Server erstellen
            this.server = net.createServer((socket) => {
                const clientIP = socket.remoteAddress || t.unknownAddress;
                const clientPort = socket.remotePort || t.unknownPort;

                // Client-Informationen in der Map speichern
                this.clients.set(socket, { ip: clientIP, port: clientPort });

                // Logging: Neue Verbindung
                if (isLogIpsEnabled) {
                    if (!isanonymousModeEnabled) logEvent(clientIP, clientPort, 'Connection New', t.connectionNew, 'info');
                } else {
                    if (!isanonymousModeEnabled) logEvent('*****', '****', 'Connection New', t.connectionNew, 'info');
                }

                // Ereignis: Daten empfangen
                socket.on('data', async (data) => {
                    const client = this.clients.get(socket);
                    if (isLogIpsEnabled) {
                        if (!isanonymousModeEnabled) logEvent(client.ip, client.port, 'Data Received', t.dataReceivedMsg.replace('${data}', data.toString()), 'info' );
                    } else {
                        if (!isanonymousModeEnabled) logEvent('*****', '****', 'Data Received', t.dataReceivedMsg.replace('${data}', data.toString()), 'info' );
                    }

                    try {
                        const message = JSON.parse(data.toString());
                        const response = await onMessage(message);
                        socket.write(JSON.stringify(response));

                        // Logging: Erfolgreiche Antwort
                        if (isLogIpsEnabled) {
                            if (!isanonymousModeEnabled) logEvent(client.ip, client.port, 'Response Sent', t.responseSentSuccess, 'info');
                        } else {
                            if (!isanonymousModeEnabled) logEvent('*****', '****', 'Response Sent', t.responseSentSuccess, 'info');
                        }

                    } catch (err) {
                        if (isLogIpsEnabled) {
                            if (!isanonymousModeEnabled) logEvent(client.ip, client.port, 'Error Processing Message', t.errorProcessingMsg.replace('${error}', err.message || err), 'error' );
                        } else {
                            if (!isanonymousModeEnabled) logEvent('*****', '****', 'Error Processing Message', t.errorProcessingMsg.replace('${error}', err.message || err), 'error' );
                        }
                        socket.write(JSON.stringify({ error: t.invalidMessage }));
                    }
                });

                // Ereignis: Verbindung geschlossen
                socket.on('close', () => {
                    const client = this.clients.get(socket);
                    if (isLogIpsEnabled) {
                        if (!isanonymousModeEnabled) logEvent(client.ip, client.port, 'Connection Closed', t.connectionClosed, 'info');
                    } else {
                        if (!isanonymousModeEnabled) logEvent('*****', '****', 'Connection Closed', t.connectionClosed, 'info');
                    }
                    this.clients.delete(socket); // Client aus der Map entfernen
                });

                // Fehlerbehandlung für einzelne Sockets
                socket.on('error', (err) => {
                    const client = this.clients.get(socket);
                    if (!isanonymousModeEnabled) logEvent(
                        client?.ip || 'unknown',
                        client?.port || 'unknown',
                        'Socket Error',
                        t.socketErrorPrefix + ' ' + (err.message || err),
                        'error'
                    );
                });

                // Server-Ereignis: Verbindung hergestellt
                this.server.on('connection', (socket) => {
                    if (!isanonymousModeEnabled) logEvent('server', socket.remotePort || 'unknown', 'Connection Established', t.connectionEstablished, 'info');
                    socket.setKeepAlive(true, 30000); // Keep-Alive für jede Verbindung setzen
                });
            });

            // Server starten
            this.server.listen(this.port, () => {
                if (!isanonymousModeEnabled) logEvent(
                    'server', this.port, 'Server Start',
                    t.serverListeningOnPort.replace('${port}', this.port),
                    'info'
                );
                resolve();
            });

            // Server-Ereignis: Fehler
            this.server.on('error', (err) => {
                if (!isanonymousModeEnabled) logEvent(
                    'server', this.port, 'Server Error',
                    t.genericServerErrorPrefix + ' ' + (err.message || err),
                    'error'
                );
                reject(err);
            });
        });
    }

    async stop() {
        if (this.server) {
            this.server.close(() => {
                if (!isanonymousModeEnabled) logEvent('server', this.port, 'Server Stopped', t.serverStoppedLog, 'info');
                this.clients.clear(); // Alle Clients aus der Map entfernen
            });
        }
    }
}

class PrivateGPTServer {
    constructor() {
        this.server = new Server({
            name: 'pgpt-mcp-server',
            version: '2.1.0',
        }, {
            capabilities: {
                resources: {},
                tools: {},
            },
        });

        const axiosConfig = {
          baseURL: apiUrl,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          httpsAgent: new https.Agent({
            rejectUnauthorized: isSSLValidationEnabled
          })
        };

        // Conditionally Header setzen, wenn USE_PROXY = true
        if (useProxy) {
            // Nur wenn der Proxy in der envConfig aktiviert ist,
            // wird der spezielle Header gesetzt
            axiosConfig.headers['X-Custom-Header'] = customHeaderValue;
        } else {
            // Falls du sicherstellen willst, dass der Header *nicht* gesetzt wird:
            delete axiosConfig.headers['X-Custom-Header'];
        }

        // Axios-Instanz anlegen
        this.axiosInstance = axios.create(axiosConfig);
       
        // Interceptors für Logging von Requests und Responses
        this.axiosInstance.interceptors.request.use((config) => {
            const headers = { ...config.headers };
            if (headers.Authorization) {
                // Prüfen, ob es sich um Bearer oder Basic handelt
                if (headers.Authorization.startsWith('UUDBearer ')) {
                    // Bearer maskieren
                    headers.Authorization = 'Bearer ********';
                } else if (headers.Authorization.startsWith('Basic ')) {
                    // Basic maskieren
                    headers.Authorization = 'Basic ********';
                } 
            }
            if (!isanonymousModeEnabled) logEvent('axios', 'N/A', 'Request Headers', `Headers: ${JSON.stringify(headers)}`, 'info');

            return config;
        }, (error) => {
            if (!isanonymousModeEnabled) logEvent('axios', 'N/A', 'Request Error', `${t.errorPrefix} ${error.message || error}`, 'error');
            return Promise.reject(error);
        });
        
        this.axiosInstance.interceptors.response.use((response) => {
            if (!isanonymousModeEnabled) logEvent('axios', 'N/A', 'Response Received', `Status: ${response.status}`, 'info');
            return response;
        }, (error) => {
            const errorMsg = error.response ? JSON.stringify(error.response.data) : error.message;
            if (!isanonymousModeEnabled) logEvent('axios', 'N/A', 'Response Error', `Fehler: ${errorMsg}`, 'error');
            return Promise.reject(error);
        });

        this.setupResourceHandlers();
        this.setupToolHandlers();

        // Fehlerbehandlung
        this.server.onerror = (error) => {
            if (!isanonymousModeEnabled) logEvent(
                'server',
                'N/A',
                'MCP Error',
                t.mcpErrorPrefix.replace('${error}', error.message || JSON.stringify(error, null, 2)),
                'error'
            );
        };

        process.on('SIGINT', async () => {
            await this.server.close();
            if (!isanonymousModeEnabled) logEvent('process', 'N/A', 'Shutdown', t.serverShutdownLog, 'info');
            process.exit(0);
        });
    }
    async ensureAuthenticated(token) {
        if (this.axiosInstance.defaults.headers.common['Authorization']) {
            delete this.axiosInstance.defaults.headers.common['Authorization'];
        }
        this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }

    /**
     * Login-Funktion mit Logging
     * @param {string} email - Benutzer-E-Mail
     * @param {string} password - Benutzer-Passwort
     * @returns {string} - Authentifizierungs-Token
     */
    async login(email, password) {
        if (!isanonymousModeEnabled) logEvent(email, 'N/A', 'Login', t.authStarted, 'info');
        try {
            const loginResponse = await this.axiosInstance.post('/login', {
                email,
                password
            });
            if (!isanonymousModeEnabled) logEvent(
                email,
                'N/A',
                'Login Response',
                t.loginTokenReceived.replace('${token}', loginResponse.data.data.token),
                'info'
            );
            return loginResponse.data.data.token;
        } catch (error) {
            if (!isanonymousModeEnabled) logEvent(
                email,
                'N/A',
                'Login Error',
                t.loginErrorPrefix.replace('${error}', error.message || error),
                'error'
            );
            throw new Error(t.authFailed);
        }
    }


    /**
     * Authentifizierung sicherstellen mit Logging
     * @param {string} token - Authentifizierungs-Token
     */
    async ensureAuthenticated(token) {
        if (!token) {
            if (!isanonymousModeEnabled) logEvent('auth', 'N/A', 'Ensure Authenticated', t.missingTokenAuth, 'error');
            throw new Error(t.missingTokenError);
        }

        if (!isanonymousModeEnabled) logEvent('auth', 'N/A', 'Set Token', t.settingToken, 'info');

        // Entferne den Basic Auth Header, falls vorhanden
        if (this.axiosInstance.defaults.headers.common['Authorization']) {
            delete this.axiosInstance.defaults.headers.common['Authorization'];
        }

    // Setze das Token als Authorization-Header
    this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    if (!isanonymousModeEnabled) logEvent('auth', 'N/A', 'Set Token', t.tokenSetSuccess, 'info');
}


    /**
     * Gruppen validieren mit Logging
     * @param {Array} groups - Gruppenliste
     * @param {string} token - Authentifizierungs-Token
     * @returns {Object} - Validierungsergebnis
     */
    async validateGroups(groups, token) {
        try {
            if (!isanonymousModeEnabled) logEvent(
                'validateGroups',
                'N/A',
                'Checking Groups',
                t.checkingGroups.replace('${groups}', JSON.stringify(groups)),
                'info'
            );
            if (!token) {
                if (!isanonymousModeEnabled) logEvent('validateGroups', 'N/A', 'Error', t.missingTokenError, 'error');
                throw new Error(t.missingTokenGroups);
            }

            const response = await this.axiosInstance.get('/groups', {
                headers: { Authorization: `Bearer ${token}` }
            });

            const availableGroups = response.data?.data?.assignableGroups || [];
            if (!isanonymousModeEnabled) logEvent('validateGroups', 'N/A', 'Available Groups', `Verfügbar: ${JSON.stringify(availableGroups)}`, 'info');

            const invalidGroups = groups.filter(group => !availableGroups.includes(group));
            if (invalidGroups.length > 0) {
                if (!isanonymousModeEnabled) logEvent(
                    'validateGroups',
                    'N/A',
                    'Invalid Groups',
                    t.invalidGroupsLog.replace('${groups}', JSON.stringify(invalidGroups)),
                    'error'
                );
                return { isValid: false, invalidGroups };
            }
            if (!isanonymousModeEnabled) logEvent('validateGroups', 'N/A', 'Validation Success', t.allGroupsValid, 'info');
            return { isValid: true };
        } catch (error) {
            const errorMessage = error.response?.data || error.message;
            if (!isanonymousModeEnabled) logEvent(
                'validateGroups',
                'N/A',
                'Group Validation Error',
                t.groupValidationErrorPrefix.replace('${error}', errorMessage),
                'error'
            );
            throw new Error(
                error.response?.data?.message || t.fetchGroupsErrorBackup
            );
        }
    }
    setupResourceHandlers() {
        // List available resources
        this.server.setRequestHandler(ListResourcesRequestSchema, async () => ({
            resources: []
        }));
        // List resource templates
        this.server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
            resourceTemplates: []
        }));
        // Read resource
        this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
            if (!request.params?.uri) {
                throw new McpError(
                    ErrorCode.InvalidRequest,
                    t.missingUriParameter
                );
            }
            throw new McpError(ErrorCode.InvalidRequest, `Invalid URI: ${request.params.uri}`);
        });
    }

    setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
            tools: [
            {   /* 1.0 Login #####################################################################################*/
                name: 'login',
                description: 'User login to retrieve an API token',
                inputSchema: {
                    type: 'object',
                    properties: {
                        email: {
                            type: 'string',
                            description: 'User email address for login'
                        },
                        password: {
                            type: 'string',
                            description: 'User password for login'
                        }
                    },
                    required: ['email', 'password']
                }
            },
            {   /* 1.1 Logout ####################################################################################*/
                name: 'logout',
                description: 'Invalidate the API token',
                inputSchema: { type: 'object', properties: {} },
            },
            {   /* 2.0 Chat ######################################################################################*/
                name: 'chat',
                description: 'Start or continue a chat with PrivateGPT with optional RAG capabilities',
                inputSchema: {
                    type: 'object',
                    properties: {
                        question: { type: 'string', description: 'The question or prompt to send' },
                        usePublic: { type: 'boolean', description: 'Use public knowledge base', default: false },
                        groups: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Group names for RAG (exclusive with usePublic)',
                        },
                        language: { type: 'string', description: 'Language code (e.g., "en")', default: 'en' },
                    },
                    required: ['question'],
                },
            },
            {   /* 2.1 Continue Chat #############################################################################*/
                name: 'continue_chat',
                description: 'Continue an existing chat',
                inputSchema: {
                    type: 'object',
                    properties: {
                        chatId: { type: 'string', description: 'ID of the existing chat to continue' },
                        question: { type: 'string', description: 'The next question or message in the chat' },
                    },
                    required: ['chatId', 'question'],
                },
            },
            {   /* 2.2 Get Chat Info #############################################################################*/
                name: 'get_chat_info',
                description: 'Retrieve details about an existing chat using its ID',
                inputSchema: {
                    type: 'object',
                    properties: {
                        chatId: { type: 'string', description: 'ID of the chat to retrieve details for' },
                        token: { type: 'string', description: 'Authorization token for API access' },
                    },
                    required: ['chatId', 'token'],
                },
            },
            {   /* 3.0 Create Source #############################################################################*/
                name: 'create_source',
                description: 'Create a new source with automatic markdown formatting',
                inputSchema: {
                    type: 'object',
                    properties: {
                        name: { type: 'string', description: 'Name of the source' },
                        content: { type: 'string', description: 'Markdown-formatted content' },
                        groups: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Optional groups to assign the source to',
                        },
                    },
                    required: ['name', 'content'],
                },
            },
            {   /* 3.1 Get Source ################################################################################*/
                name: 'get_source',
                description: 'Retrieve information about a specific source',
                inputSchema: {
                    type: 'object',
                    properties: {
                        sourceId: { type: 'string', description: 'ID of the source to retrieve' },
                    },
                    required: ['sourceId'],
                },
            },
            {   /* 3.2 List Sources ##############################################################################*/
                name: 'list_sources',
                description: 'List all sources in a specific group',
                inputSchema: {
                    type: 'object',
                    properties: {
                        groupName: { type: 'string', description: 'Group name to list sources from' },
                    },
                    required: ['groupName'],
                },
            },
            {   /* 3.3 Edit Source ###############################################################################*/
                name: 'edit_source',
                description: 'Edit an existing source',
                inputSchema: {
                    type: 'object',
                    properties: {
                        sourceId: {
                            type: 'string',
                            description: 'ID of the source to edit'
                        },
                        token: {
                            type: 'string',
                            description: 'Authorization token for API access'
                        },
                        title: {
                            type: 'string',
                            description: 'New title for the source (optional)'
                        },
                        content: {
                            type: 'string',
                            description: 'New markdown-formatted content for the source (optional)'
                        },
                        groups: {
                            type: 'array',
                            items: {
                                type: 'string'
                            },
                            description: 'Updated group(s) to assign to the source (optional)'
                        }
                    },
                    required: ['sourceId', 'token']
                }
            },
            {   /* 3.4 Delete Source #############################################################################*/
                name: 'delete_source',
                description: 'Delete a specific source',
                inputSchema: {
                    type: 'object',
                    properties: {
                        sourceId: { type: 'string', description: 'ID of the source to delete' },
                    },
                    required: ['sourceId'],
                },
            },
            {   /* 4.0 List Groups ###############################################################################*/
                name: 'list_groups',
                description: 'Retrieve personal and assignable groups',
                inputSchema: { type: 'object', properties: {} },
            },
            {   /* 4.1 Store Group ###############################################################################*/
                name: 'store_group',
                description: 'Create a new group',
                inputSchema: {
                    type: 'object',
                    properties: {
                        groupName: { type: 'string', description: 'Name of the new group' },
                        description: { type: 'string', description: 'Description of the new group' },
                    },
                    required: ['groupName'],
                },
            },
            {   /* 4.2 Delete Group ##############################################################################*/
                name: 'delete_group',
                description: 'Delete an existing group',
                inputSchema: {
                    type: 'object',
                    properties: {
                        groupName: { type: 'string', description: 'Name of the group to delete' },
                    },
                    required: ['groupName'],
                },
            },
            {   /* 5.0 Store User ################################################################################*/
                name: 'store_user',
                description: 'Create a new user',
                inputSchema: {
                    type: 'object',
                    properties: {
                        name: { type: 'string', description: 'Name of the user' },
                        email: { type: 'string', description: 'Email of the user' },
                        password: { type: 'string', description: 'Password for the user' },
                        language: { type: 'string', description: 'Preferred language (optional)', default: 'en' },
                        timezone: { type: 'string', description: 'Timezone (optional)', default: 'Europe/Berlin' },
                        roles: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Roles to assign (optional)'
                        },
                        groups: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Groups to assign (optional)'
                        },
                        usePublic: { type: 'boolean', description: 'Enable public knowledge (optional)', default: false }
                    },
                    required: ['name', 'email', 'password']
                },
            },
            {   /* 5.1 Edit User #################################################################################*/
                name: 'edit_user',
                description: 'Edit an existing user',
                inputSchema: {
                    type: 'object',
                    properties: {
                        email: { type: 'string', description: 'Email of the user to edit' },
                        name: { type: 'string', description: 'New name for the user (optional)' },
                        password: { type: 'string', description: 'New password for the user (optional)' },
                        language: { type: 'string', description: 'Preferred language (optional)' },
                        timezone: { type: 'string', description: 'Timezone (optional)' },
                        roles: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Updated roles (optional)'
                        },
                        groups: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Updated groups (optional)'
                        },
                        usePublic: { type: 'boolean', description: 'Enable public knowledge (optional)' }
                    },
                    required: ['email']
                }
            },
            {   /* 5.2 Delete User ###############################################################################*/
                name: 'delete_user',
                description: 'Delete an existing user',
                inputSchema: {
                    type: 'object',
                    properties: {
                        email: { type: 'string', description: 'Email of the user to delete' }
                    },
                    required: ['email']
                }
            }
        ],
    }));
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            if (!request.params?.name) {
                throw new McpError(
                    ErrorCode.InvalidRequest,
                    t.missingToolName
                );
            }
            try {
                //await this.ensureAuthenticated();
                if (!isanonymousModeEnabled) logEvent(
                    'system', 'N/A', 'Handling Tool Request',
                    t.handlingToolRequest.replace('${tool}', request.params.name),
                    'info'
                );
                switch (request.params.name) {
                    /* 1.0 Login ######################################################################################*/
                    case 'login': {
                        const disabledResponse = checkToolEnabled('login');
                        if (disabledResponse) return disabledResponse;

                        const { email, password } = request.params.arguments; // Extrahiere email und password aus der Nachricht

                        if (!email || !password) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'login', t.loginMissingCredentialsAlternative, 'error');
                            return {
                                status: 'E10-R-1000',
                                message: t.loginEmailPasswordRequired
                            };
                        }

                        try {
                            // Aufruf des Login-Endpunkts der API
                            const loginResponse = await this.axiosInstance.post('/login', { email, password });

                            // Loggen des erfolgreichen Logins
                            if (!isanonymousModeEnabled) logEvent(
                                'system',
                                'N/A',
                                'loginSuccess',
                                t.loginSuccess.replace('${data}', JSON.stringify(loginResponse.data)),
                                'info'
                            );

                            // Token zurückgeben
                            return {
                                status: loginResponse.data?.status || 'ok', // Dynamisch, falls der API-Status einheitlich ist
                                message: loginResponse.data?.message || 'Login erfolgreich.', // API-Nachricht verwenden oder Standardnachricht
                                token: loginResponse.data?.data?.token // Token aus API-Antwort
                            };
                        } catch (error) {
                            const errorMessage = error.response?.data?.message || error.message || t.unknownError;

                            // Loggen des Fehlers beim Login
                            if (!isanonymousModeEnabled) logEvent(
                                'system',
                                'N/A',
                                'loginError',
                                t.loginError.replace('${error}', errorMessage),
                                'error'
                            );

                            return {
                                status: error.response?.status || 'E10-R-1001', // API-Fehlerstatus oder Standardfehlerstatus
                                message: errorMessage,
                            };
                        }
                    }
                   /* 1.1 Logout #####################################################################################*/
                    case 'logout': {
                        const disabledResponse = checkToolEnabled('logout');
                        if (disabledResponse) return disabledResponse;

                        const { token } = request.params; // Korrigiert von 'message' zu 'request.params'
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'logout', `Extrahierter Token: ${token}`, 'info');

                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        try {
                            // Setze den Bearer Token als Standard-Authorization-Header
                            await this.ensureAuthenticated(token);

                            // Console-Log für Header zu Debug-Zwecken
                            console.log('Logout Request Headers:', this.axiosInstance.defaults.headers.common);
                            const logoutResponse = await this.axiosInstance.delete('/logout', { headers: { Authorization: `Bearer ${token}` }})

                            // const logoutResponse = await this.axiosInstance.delete('/logout');

                            // Loggen des erfolgreichen Logouts
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'logoutSuccess', t.logoutSuccess.replace('${data}', JSON.stringify(logoutResponse.data)), 'info');

                            return {
                                data: {}, // Optional: Zusätzliche Daten könnten hier eingefügt werden
                                message: 'success',
                                status: 200, // OK
                            };
                        } catch (error) {
                            const logoutErrorMessage = error.response?.data || error.message;
                            // Loggen des Fehlers beim Logout
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'logoutError', t.logoutError.replace('${error}', logoutErrorMessage), 'error');

                            return {
                                data: {},
                                message: error.response?.data?.message || t.logoutFailedTryAgain,
                                status: error.response?.status || 'E11-R-1100', // Internal Server Error oder spezifischer Statuscode
                            };
                        }
                    }
                    /* 2.0 Chat #######################################################################################*/
                    case 'chat': {
                        const disabledResponse = checkToolEnabled('chat');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chat', `Extrahierter Token: ${token}`, 'info');

                        // Token prüfen und validieren
                        if (!token) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatError', t.noTokenError, 'error');
                            return { status: 'E20-R-2000', message: t.missingTokenError };
                        }

                        // Argument-Validierung
                        if (!args || !args.question) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatError', t.missingArgumentsError.replace('${args}', JSON.stringify(args)), 'error');
                            return {
                                status: 'error',
                                message: t.missingArgumentsError.replace('${args}', JSON.stringify(args)),
                            };
                        }

                        const { question, usePublic, groups, language } = args;

                        // Konflikt zwischen `usePublic` und `groups` lösen
                        if (usePublic && groups && groups.length > 0) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatWarning', t.publicGroupsConflictWarning, 'warn');
                            args.usePublic = false;
                        }

                        try {
                            // Loggen der Chat-Anfrage
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatRequest', t.sendingChatRequest
                                .replace('${question}', question)
                                .replace('${usePublic}', usePublic)
                                .replace('${groups}', JSON.stringify(groups))
                                .replace('${language}', language), 'info');

                            const response = await this.axiosInstance.post(
                                '/chats',
                                {
                                    question,
                                    usePublic: usePublic || false,
                                    groups: Array.isArray(groups) ? groups : [groups],
                                    language: language || 'de',
                                },
                                { headers: { Authorization: `Bearer ${token}` } }
                            );

                            const data = response.data?.data || {};
                            // Loggen der erfolgreichen Chat-Antwort
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatSuccess', t.chatResponseSuccess.replace('${data}', JSON.stringify(data)), 'info');

                            // Erfolgsantwort mit Status und Daten
                            return {
                                status: response.data?.status || 'ok',
                                message: response.data?.message || 'Chat erfolgreich.',
                                content: {
                                    chatId: data.chatId,
                                    answer: data.answer,
                                    sources: data.sources || [],
                                },
                            };
                        } catch (error) {
                            const chatApiErrorMessage = error.message || error.response?.data;
                            // Loggen des Fehlers bei der Chat-API-Anfrage
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatApiError', t.chatApiError.replace('${error}', chatApiErrorMessage), 'error');

                            // Fehlerantwort mit Status und Nachricht
                            return {
                                status: error.response?.status || 'E20-R-2002',
                                message: error.response?.data?.message || t.chatApiErrorDefault,
                            };
                        }
                    }
                    /* 2.1 Continue Chat ##############################################################################*/
                    case 'continue_chat': {
                        const disabledResponse = checkToolEnabled('continue_chat');
                        if (disabledResponse) return disabledResponse;

                        const args = request.params.arguments;

                        if (!args || !args.chatId || !args.question) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chat', t.missingChatParams, 'error');
                            return {
                              status: 'E21-R-2100',
                              message: t.missingChatParams
                            };
                        }

                        const { chatId, question } = args;
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chat', t.conversationContinuation.replace('${chatId}', chatId), 'info');

                        try {
                            const continueChatResponse = await this.axiosInstance.patch(`/chats/${chatId}`, {
                                question: question,
                            });
                            // Loggen der erfolgreichen Fortsetzung der Konversation
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chatSuccess', t.conversationSuccess.replace('${data}', JSON.stringify(continueChatResponse.data, null, 2)), 'info');
                            return {
                                content: {
                                    chatId:  continueChatResponse.data.data.chatId,
                                    answer:  continueChatResponse.data.data.answer,
                                    sources: continueChatResponse.data.sources || [],
                                    message: continueChatResponse.data.message,
                                    status:  continueChatResponse.data.status,
                                },
                            };
                        } catch (error) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chatError', t.apiRequestError.replace('${error}', error.message), 'error');
                            return {
                              status: error.response?.status || 'E21-R-2101',
                              message: error.response?.data?.message || t.continueConversationError,
                            };
                        }
                    }
                    /* 2.2 Get Chat Info ##############################################################################*/
                    case 'get_chat_info': {
                        const disabledResponse = checkToolEnabled('get_chat_info');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;

                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        const { chatId } = args;

                        if (!chatId) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_info', 'chatId ist erforderlich, um Chat-Informationen abzurufen.', 'error');
                            return { status: 'E22-R-2200', message: 'chatId ist erforderlich, um Chat-Informationen abzurufen.' };
                        }

                        try {
                            const response = await this.axiosInstance.get(`/chats/${chatId}`, {
                                headers: { Authorization: `Bearer ${token}` }
                            });

                            const chatData = response.data?.data;

                            if (!chatData) {
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_info', t.noChatData, 'error');
                                return {
                                    status: 'E22-R-2201',
                                    message: t.noChatData,
                                };
                            }

                            // Loggen der abgerufenen Chat-Informationen
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_infoSuccess', `Chat-Informationen abgerufen: ${JSON.stringify(chatData)}`, 'info');

                            return {
                                data: {
                                    chatId: chatData.chatId,
                                    title: chatData.title || 'Unbenannter Chat',
                                    language: chatData.language || 'Unbekannt',
                                    groups: chatData.groups || [],
                                    messages: chatData.messages || []
                                },
                                message: response.data?.message || 'Erfolgreich abgerufen.'
                            };
                        } catch (error) {
                            const fetchChatErrorMessage = error.message || error.response?.data;
                            // Loggen des Fehlers beim Abrufen der Chat-Informationen
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_infoError', t.fetchChatInfoError.replace('${error}', fetchChatErrorMessage), 'error');
                            return {
                                status: 'E22-R-2202',
                                message: error.response?.data?.message || 'Fehler beim Abrufen der Chat-Informationen.'
                            };
                        }
                    }
                    /* 3.0 Create Source ##############################################################################*/
                    case 'create_source': {
                        const disabledResponse = checkToolEnabled('create_source');
                        if (disabledResponse) return disabledResponse;

                        const args = request.params.arguments;
                        const token = request.params.token;

                        // Validierung: Erforderliche Parameter prüfen
                        if (!token) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_source', t.tokenMissing, 'error');
                            return { status: 'E30-R-3000', message: t.missingTokenError };
                        }
                        if (!args || !args.name || !args.content) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_source', t.missingNameAndContent, 'error');
                            return {
                              status: 'E30-R-3001',
                              message: t.missingNameAndContent
                            };
                        }

                        const { name, content, groups } = args;

                        try {
                            // Token im Header setzen
                            this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;

                            // Gruppenvalidierung vorab durchführen
                            if (groups && groups.length > 0) {
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceGroupCheck', `Überprüfen der Gruppen: ${JSON.stringify(groups)}`, 'info');

                                const response = await this.axiosInstance.get('/groups');
                                const availableGroups = response.data?.data?.assignableGroups || [];

                                // Ungültige Gruppen ermitteln
                                const invalidGroups = groups.filter(group => !availableGroups.includes(group));
                                if (invalidGroups.length > 0) {
                                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceInvalidGroups', `Ungültige Gruppen gefunden: ${invalidGroups.join(', ')}`, 'error');
                                    return {
                                        status: 'E30-R-3002',
                                        message: `Ungültige Gruppen: ${invalidGroups.join(', ')}`,
                                    };
                                }
                            }

                            // API-Aufruf zur Erstellung der Quelle
                            const createSourceResponse = await this.axiosInstance.post(
                                '/sources',
                                { name, content, groups },
                                { headers: { Authorization: `Bearer ${token}` } }
                            );

                            // Loggen der erfolgreichen Erstellung der Quelle
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceSuccess', `Quelle erfolgreich erstellt: ${JSON.stringify(createSourceResponse.data)}`, 'info');

                            // Erfolgsantwort
                            return {
                                status: createSourceResponse.data?.status || 'ok',
                                message: createSourceResponse.data?.message || 'Quelle erfolgreich erstellt.',
                                data: createSourceResponse.data?.data,
                            };
                        } catch (error) {
                            const createSourceError = error.response?.data || error.message;
                            // Loggen des Fehlers bei der Erstellung der Quelle
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceError', t.createSourceError.replace('${error}', createSourceError), 'error');

                            // Fehlerhafte Antwort
                            if (error.response) {
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceResponseError', `Status: ${error.response.status}, Data: ${JSON.stringify(error.response.data)}`, 'error');
                                return {
                                    status: 'E30-R-3003',
                                    message: error.response.data?.message || 'Ein Fehler ist aufgetreten.',
                                    details: {
                                        status: error.response.status,
                                        headers: error.response.headers,
                                        data: error.response.data,
                                    },
                                };
                            } else if (error.request) {
                                if (!isanonymousModeEnabled) logEvent(
                                  'system',
                                  'N/A',
                                  'create_sourceNoResponse',
                                  t.noServerResponse + ` ${JSON.stringify(error.request)}`,
                                  'error'
                                );

                                return {
                                    status: 'E30-R-3004',
                                    message: t.noServerResponse,
                                    details: { request: error.request },
                                };
                            } else {
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceUnknownError', `Unbekannter Fehler: ${error.message}`, 'error');
                                return {
                                    status: 'E30-R-3005',
                                    message: error.message || unknownError,
                                };
                            }
                        }
                    }
                    /* 3.1 Get Source #################################################################################*/
                    case 'get_source': {
                        const disabledResponse = checkToolEnabled('get_source');
                        if (disabledResponse) return disabledResponse;

                        const args = request.params.arguments;
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_sourceRequest', t.makingGetSourceRequest.replace('${args}', JSON.stringify(args, null, 2)), 'info');

                        try {
                            const getSourceResponse = await this.axiosInstance.get(`/sources/${args.sourceId}`);
                            // Loggen der erhaltenen Quellenantwort
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_sourceSuccess', t.gotGetSourceResponse.replace('${data}', JSON.stringify(getSourceResponse.data, null, 2)), 'info');
                            return {
                                content: [
                                    {
                                        type: 'text',
                                        text: JSON.stringify(getSourceResponse.data, null, 2)
                                    }
                                ]
                            };
                        } catch (error) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_sourceError', t.errorHandlingRequest.replace('${error}', error.message || JSON.stringify(error, null, 2)), 'error');
                            return {
                                status: 'E31-R-3151',
                                message: t.apiErrorDetails
                                    .replace('${status}', error.response?.status || 'E31-R-3151')
                                    .replace('${data}', JSON.stringify(error.response?.data || {}, null, 2)),
                            };
                        }
                    }
                    /* 3.2 List Sources ##############################################################################*/
                    case 'list_sources': {
                        const disabledResponse = checkToolEnabled('list_sources');
                        if (disabledResponse) return disabledResponse;

                        const args = request.params.arguments;
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sourcesRequest', t.makingListSourcesRequest.replace('${args}', JSON.stringify(args, null, 2)), 'info');

                        try {
                            const listSourcesResponse = await this.axiosInstance.post('/sources/groups', {
                                groupName: args.groupName
                            });
                            // Loggen der erhaltenen Quellenliste
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sourcesSuccess', t.gotListSourcesResponse.replace('${data}', JSON.stringify(listSourcesResponse.data, null, 2)), 'info');
                            return {
                                content: [
                                    {
                                        type: 'text',
                                        text: JSON.stringify(listSourcesResponse.data, null, 2)
                                    }
                                ]
                            };
                        } catch (error) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sourcesError', t.apiRequestError.replace('${error}', error.message || JSON.stringify(error, null, 2)), 'error');
                            return {
                              status: 'E32-R-3251',
                              message: error.response?.data?.message || t.fetchSourcesError,
                            };
                        }
                    }
                    /* 3.3 Edit Source ################################################################################*/
                    case 'edit_source': {
                        const disabledResponse = checkToolEnabled('edit_source');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;
                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        // Mindestens die E-Mail muss angegeben sein, um den User zu identifizieren
                        if (!args || !args.email) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_user', 'Die E-Mail des Benutzers ist erforderlich, um den Datensatz zu bearbeiten.', 'error');
                            return {
                                status: 'E51-R-5100',
                                message: 'Die E-Mail des Benutzers ist erforderlich, um den Datensatz zu bearbeiten.'
                            };
                        }

                        try {
                            // Nur Felder senden, die tatsächlich aktualisiert werden sollen
                            const payload = {};
                            if (args.name) payload.name = args.name;
                            if (args.password) payload.password = args.password;
                            if (args.language) payload.language = args.language;
                            if (args.timezone) payload.timezone = args.timezone;
                            if (Array.isArray(args.roles)) payload.roles = args.roles;
                            if (Array.isArray(args.groups)) payload.groups = args.groups;
                            if (typeof args.usePublic === 'boolean') payload.usePublic = args.usePublic;

                            // E-Mail ist Pflicht, um den Benutzer auf dem Server zu finden
                            payload.email = args.email;

                            const response = await this.axiosInstance.patch(
                                '/users',
                                payload,
                                {
                                    headers: { Authorization: `Bearer ${token}` }
                                }
                            );

                            // Loggen der erfolgreichen Benutzerbearbeitung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userSuccess', `Benutzer erfolgreich bearbeitet: ${JSON.stringify(response.data)}`, 'info');

                            return {
                                status: response.data?.status || 'ok',
                                message: response.data?.message || 'Benutzer erfolgreich bearbeitet.',
                                data: response.data?.data
                            };
                        } catch (error) {
                            const editUserError = error.response?.data || error.message;
                            // Loggen des Fehlers bei der Benutzerbearbeitung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userError', t.editUserError.replace('${error}', editUserError), 'error');
                            return {
                                status: error.response?.status || 'E51-R-5101',
                                message: error.response?.data?.message || 'Fehler beim Bearbeiten des Benutzers.'
                            };
                        }
                    }
                    /* 3.4 Delete Source ##############################################################################*/
                    case 'delete_source': {
                        const disabledResponse = checkToolEnabled('delete_source');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;

                        // Validierung: Token erforderlich
                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        const { sourceId } = args;

                        // Validierung: sourceId erforderlich
                        if (!sourceId) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_source', 'sourceId ist erforderlich, um eine Quelle zu löschen.', 'error');
                            return {
                                data: {},
                                message: t.missingParameterError.replace('${parameter}', 'sourceId'),
                                status: 'E34-R-3400', // Bad Request
                            };
                        }

                        try {
                            // API-Aufruf: Quelle löschen
                            const deleteResponse = await this.axiosInstance.delete(`/sources/${sourceId}`, {
                                headers: { Authorization: `Bearer ${token}` },
                            });

                            // Loggen der erfolgreichen Quellenlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_sourceSuccess', t.deleteSourceSuccess.replace('${data}', JSON.stringify(deleteResponse.data, null, 2)), 'info');

                            // Erfolgreiche Antwort
                            return {
                                data: deleteResponse.data?.data || {}, // Optionale Daten aus der API
                                message: deleteResponse.data?.message || 'Quelle erfolgreich gelöscht.',
                                status: deleteResponse.status || 200, // OK
                            };
                        } catch (error) {
                            // Loggen des Fehlers bei der Quellenlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_sourceError', t.deleteSourceError.replace('${error}', error.message || JSON.stringify(error.response?.data)), 'error');

                            return {
                                data: {},
                                message: error.response?.data?.message || t.deleteSourceFailedTryAgain,
                                status: error.response?.status || 'E34-R-3401',
                            };
                        }
                    }
                    /* 4.0 List Groups ################################################################################*/
                    case 'list_groups': {
                        const disabledResponse = checkToolEnabled('list_groups');
                        if (disabledResponse) return disabledResponse;

                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsRequest', t.makingListGroupsRequest, 'info');

                        try {
                            const listGroupsResponse = await this.axiosInstance.get('/groups');
                            // Loggen der erfolgreichen Gruppenliste
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsSuccess', t.gotListGroupsResponse.replace('${data}', JSON.stringify(listGroupsResponse.data)), 'info');
                            return {
                                content: [
                                    {
                                        type: 'text',
                                        text: JSON.stringify(listGroupsResponse.data, null, 2)
                                    }
                                ]
                            };
                        } catch (error) {
                            const fetchGroupsError = error.message || JSON.stringify(error.response?.data);
                            // Loggen des Fehlers beim Abrufen der Gruppen
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsError', t.fetchGroupsError.replace('${error}', fetchGroupsError), 'error');
                            return {
                                status: 'E40-R-4051',
                                message: `${t.fetchGroupsErrorPrefix} ${error.response?.data?.message || t.unknownError}`,
                            };
                        }
                    }
                    /* 4.1 Store Group ################################################################################*/
                    case 'store_group': {
                        const disabledResponse = checkToolEnabled('store_group');
                        if (disabledResponse) return disabledResponse;
                        const args = request.params.arguments;

                        if (!args || !args.groupName) {
                            throw new McpError(
                              ErrorCode.InvalidRequest,
                              t.missingGroupParameterStore
                            );
                        }

                        // Loggen des Beginns der Gruppenspeicherung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupRequest', t.storeGroupLog
                            .replace('${groupName}', args.groupName)
                            .replace('${description}', args.description || t.noDescriptionProvided), 'info');

                        try {
                            const storeGroupResponse = await this.axiosInstance.post('/groups', {
                                groupName: args.groupName,
                                description: args.description || ''
                            });
                            // Loggen der erfolgreichen Gruppenspeicherung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupSuccess', t.storeGroupSuccess.replace('${data}', JSON.stringify(storeGroupResponse.data, null, 2)), 'info');

                            return {
                                content: [
                                    {
                                        type: 'text',
                                        text: `Gruppe "${args.groupName}" erfolgreich erstellt mit ID: ${storeGroupResponse.data.id}`
                                    }
                                ]
                            };
                        } catch (error) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupError', t.errorHandlingRequest.replace('${error}', error.message || JSON.stringify(error, null, 2)), 'error');
                            if (axios.isAxiosError(error)) {
                                const message = error.response?.data?.message ?? error.message;
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupApiError', t.apiErrorDetails.replace('${status}', error.response?.status || 'E41-R-4100').replace('${data}', JSON.stringify(error.response?.data || {}, null, 2)), 'error');
                                return {
                                    content: [
                                        {
                                            type: 'text',
                                            text: `API-Fehler: ${message}`
                                        }
                                    ],
                                    isError: true
                                };
                            }
                            throw error;
                        }
                    };
                    /* 4.2 Delete Group ###############################################################################*/
                    case 'delete_group': {
                        const disabledResponse = checkToolEnabled('delete_group');
                        if (disabledResponse) return disabledResponse;

                        const { groupName } = request.params.arguments; // Extrahiere die Gruppe
                        if (!groupName) {
                            throw new McpError(
                                ErrorCode.InvalidRequest,
                                t.missingGroupParameterDelete
                            );
                        }

                        // Loggen des Beginns der Gruppenlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupRequest', t.deleteGroupLog.replace('${groupName}', groupName), 'info');

                        try {
                            // API-Aufruf mit dem notwendigen JSON-Body
                            const deleteGroupResponse = await this.axiosInstance.delete('/groups', {
                                data: { groupName }, // JSON-Body für den DELETE-Request
                            });

                            // Loggen der erfolgreichen Gruppenlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupSuccess', t.deleteGroupSuccessLog.replace('${data}', JSON.stringify(deleteGroupResponse.data)), 'info');

                            return {
                                content: [
                                    {
                                        type: 'text',
                                        text: `Gruppe "${groupName}" wurde erfolgreich gelöscht.`,
                                    },
                                ],
                            };
                        } catch (error) {
                            // Loggen des Fehlers bei der Gruppenlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupError', t.apiRequestError.replace('${error}', error.message || JSON.stringify(error.response?.data)), 'error');
                            if (axios.isAxiosError(error)) {
                                const message = error.response?.data?.message || 'Fehler beim Löschen der Gruppe.';
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupApiError', t.apiErrorDetails.replace('${status}', error.response?.status || 'E41-R-4100').replace('${data}', JSON.stringify(error.response?.data || {}, null, 2)), 'error');
                                return {
                                    content: [
                                        {
                                            type: 'text',
                                            text: `API-Fehler: ${message}`,
                                        },
                                    ],
                                    isError: true,
                                };
                            }
                            throw new McpError(
                                ErrorCode.InternalError,
                                t.deleteGroupInternalError
                            );
                        }
                    }
                    /* 5.0 Store User #################################################################################*/
                    case 'store_user': {
                        const disabledResponse = checkToolEnabled('store_user');
                        if (disabledResponse) return disabledResponse;

                        // Token und Argumente aus request.params entnehmen
                        const { token, arguments: args } = request.params;

                        // Token validieren
                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        // Erforderliche Felder prüfen
                        if (!args || !args.name || !args.email || !args.password) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_user', t.missingNameEmailPwd, 'error');
                            return {
                              status: 'E50-R-5000',
                              message: t.missingNameEmailPwd
                            };
                        }

                        try {
                            // Benutzer anlegen
                            const response = await this.axiosInstance.post(
                                '/users',
                                {
                                    name: args.name,
                                    email: args.email,
                                    password: args.password,
                                    language: args.language || 'en',
                                    timezone: args.timezone || 'Europe/Berlin',
                                    roles: args.roles || [],
                                    groups: args.groups || [],
                                    usePublic: args.usePublic || false
                                },
                                {
                                    headers: {
                                        Authorization: `Bearer ${token}`
                                    }
                                }
                            );

                            // Loggen der erfolgreichen Benutzererstellung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_userSuccess', `Benutzer erfolgreich erstellt: ${JSON.stringify(response.data)}`, 'info');

                            // Erfolgreiche Antwort
                            return {
                                status: response.data?.status || 'ok',
                                message: response.data?.message || 'Benutzer erfolgreich erstellt.',
                                data: response.data?.data
                            };
                        } catch (error) {
                            // Loggen des Fehlers bei der Benutzererstellung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_userError', t.createUserError.replace('${error}', error.response?.data || error.message), 'error');
                            return {
                                status: error.response?.status || 'E50-R-5001',
                                message: error.response?.data?.message || 'Fehler beim Erstellen des Benutzers.'
                            };
                        }
                    }
                    /* 5.1 Edit User ##################################################################################*/
                    case 'edit_user': {
                        const disabledResponse = checkToolEnabled('edit_user');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;
                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        // Mindestens die E-Mail muss angegeben sein, um den User zu identifizieren
                        if (!args || !args.email) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_user', 'Die E-Mail des Benutzers ist erforderlich, um den Datensatz zu bearbeiten.', 'error');
                            return {
                                status: 'E51-R-5100',
                                message: 'Die E-Mail des Benutzers ist erforderlich, um den Datensatz zu bearbeiten.'
                            };
                        }

                        try {
                            // Nur Felder senden, die tatsächlich aktualisiert werden sollen
                            const payload = {};
                            if (args.name) payload.name = args.name;
                            if (args.password) payload.password = args.password;
                            if (args.language) payload.language = args.language;
                            if (args.timezone) payload.timezone = args.timezone;
                            if (Array.isArray(args.roles)) payload.roles = args.roles;
                            if (Array.isArray(args.groups)) payload.groups = args.groups;
                            if (typeof args.usePublic === 'boolean') payload.usePublic = args.usePublic;

                            // E-Mail ist Pflicht, um den Benutzer auf dem Server zu finden
                            payload.email = args.email;

                            const response = await this.axiosInstance.patch(
                                '/users',
                                payload,
                                {
                                    headers: { Authorization: `Bearer ${token}` }
                                }
                            );

                            // Loggen der erfolgreichen Benutzerbearbeitung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userSuccess', `Benutzer erfolgreich bearbeitet: ${JSON.stringify(response.data)}`, 'info');

                            return {
                                status: response.data?.status || 'ok',
                                message: response.data?.message || 'Benutzer erfolgreich bearbeitet.',
                                data: response.data?.data
                            };
                        } catch (error) {
                            const editUserError = error.response?.data || error.message;
                            // Loggen des Fehlers bei der Benutzerbearbeitung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userError', t.editUserError.replace('${error}', editUserError), 'error');
                            return {
                                status: error.response?.status || 'E51-R-5101',
                                message: error.response?.data?.message || 'Fehler beim Bearbeiten des Benutzers.'
                            };
                        }
                    }
                    /* 5.2 Delete User ################################################################################*/
                    case 'delete_user': {
                        const disabledResponse = checkToolEnabled('delete_user');
                        if (disabledResponse) return disabledResponse;

                        const { token, arguments: args } = request.params;
                        const tokenValidation = validateToken(token);
                        if (tokenValidation) return tokenValidation;

                        // E-Mail ist nötig, um den Benutzer zu löschen
                        if (!args || !args.email) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_user', t.emailRequiredForDelete, 'error');
                            return {
                                status: 'E52-R-5200',
                                message: t.emailRequiredForDelete
                            };
                        }

                        try {
                            // DELETE-Anfrage mit JSON-Body
                            const response = await this.axiosInstance.delete(
                                '/users',
                                {
                                    data: { email: args.email },
                                    headers: { Authorization: `Bearer ${token}` }
                                }
                            );

                            // Loggen der erfolgreichen Benutzerlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_userSuccess', `Benutzer erfolgreich gelöscht: ${JSON.stringify(response.data)}`, 'info');

                            return {
                                status: response.data?.status || 'ok',
                                message: response.data?.message || 'Benutzer erfolgreich gelöscht.',
                                data: response.data?.data
                            };
                        } catch (error) {
                            // Loggen des Fehlers bei der Benutzerlöschung
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_userError', t.deleteUserError.replace('${error}', error.response?.data || error.message), 'error');
                            return {
                                status: error.response?.status || 'E52-R-5201',
                                message: error.response?.data?.message || 'Fehler beim Löschen des Benutzers.'
                            };
                        }
                    }
                    default:
                        // Loggen unbekannter Befehle
                        if (!isanonymousModeEnabled) logEvent(
                            'system',
                            'N/A',
                            'unknownCommand',
                            t.unknownCommandError.replace('${cmd}', request.params.name),
                            'warn'
                        );
                        throw new McpError(
                            ErrorCode.MethodNotFound,
                            t.unknownTool.replace('${toolName}', request.params.name)
                        );
                    }
            }
            catch (error) {
                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'Unhandled Error', t.errorHandlingRequest.replace('${error}', error.message || JSON.stringify(error, null, 2)), 'error');
                if (axios.isAxiosError(error)) {
                    const message = error.response?.data?.message ?? error.message;
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'API Error Details', t.apiErrorDetails.replace('${status}', error.response?.status || 'Unknown').replace('${data}', JSON.stringify(error.response?.data || {}, null, 2)), 'error');
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `API error: ${message}`
                            }
                        ],
                        isError: true
                    };
                }
                throw error;
            }
        });
    }

 /* ##################################################################################################
   # MESSAGE HANDLER
   ##################################################################################################*/
async run() {
    const isPortInUse = (port) => new Promise((resolve, reject) => {
        const tester = net.createServer()
            .once('error', (err) => (err.code === 'EADDRINUSE' ? resolve(true) : reject(err)))
            .once('listening', () => tester.once('close', () => resolve(false)).close())
            .listen(port);
    });

    const PORT = Port;
    if (await isPortInUse(PORT)) {
        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'Port Check', t.portInUse.replace('${PORT}', PORT), 'error');
        throw new Error(t.portInUse.replace('${PORT}', PORT));
    }

    const transport = new TcpServerTransport(PORT);
    await transport.start(async (message) => {
        try {
            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'Incoming Message', `Nachricht empfangen: ${JSON.stringify(message)}`, 'info');

            // Token-Validierung nur durchführen, wenn es nicht der "login"-Befehl ist
            // if (message.command !== 'login') {
            //     const tokenValidation = validateToken(message.token);
            //     if (tokenValidation) return tokenValidation;
            // }

            if (!message || typeof message !== 'object') {
                throw new McpError(
                    ErrorCode.InvalidRequest,
                    t.invalidOrEmptyRequest
                );
            }

            // Verarbeite verschiedene Anfragen dynamisch
            if (!message.command) {
                throw new McpError(
                  ErrorCode.InvalidRequest,
                  t.missingCommandParameter
                );
            }

            switch (message.command) {
                /* 1.0 Login ######################################################################################*/
                case 'login': {
                    const disabledResponse = checkToolEnabled('login');
                    if (disabledResponse) return disabledResponse;

                    // Extrahiere die Argumente aus der Nachricht
                    const args = getArguments(message);
                    const { email, password: Pwd } = args;

                    // Überprüfe, ob die E-Mail und das Passwort vorhanden sind
                    if (!email || !Pwd) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'login', 'E-Mail und Passwort sind erforderlich.', 'error');
                        return {
                            status: 'E10-M-1050',
                            message: 'E-Mail und Passwort sind erforderlich.',
                        };
                    }

                    let password;

                    // Passwort entschlüsseln, falls erforderlich
                    if (typeof PwEncryption !== 'undefined' && PwEncryption) {
                        password = decryptPassword(Pwd);
                    } else {
                        password = Pwd;
                    }

                    try {
                        // Login-API aufrufen
                        const loginResponse = await this.axiosInstance.post('/login', { email, password });

                        // Loggen des erfolgreichen Logins
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'loginSuccess', t.loginSuccess.replace('${data}', JSON.stringify(loginResponse.data)), 'info');

                        // Entfernen des Basic Auth Headers und Setzen des Bearer Tokens
                        delete this.axiosInstance.defaults.headers.common['Authorization'];
                        this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${loginResponse.data.data.token}`;

                        // Token zurückgeben
                        return {
                            status: loginResponse.data?.status || 'ok', // Dynamisch, falls der API-Status einheitlich ist
                            message: loginResponse.data?.message || 'Login erfolgreich.', // API-Nachricht verwenden oder Standardnachricht
                            token: loginResponse.data?.data?.token, // Token aus API-Antwort
                        };
                    } catch (error) {
                        const errorMessage = error.response?.data || error.message;
                        // Loggen des Fehlers beim Login
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'loginError', t.loginError.replace('${error}', errorMessage), 'error');

                        return {
                            status: error.response?.status || 'E10-M-1051', // API-Fehlerstatus oder Standardfehlerstatus,
                            message: error.response?.data || error.message || 'no error message'
                        };
                    }
                }
                /* 1.1 Logout #####################################################################################*/
                case 'logout': {
                    const disabledResponse = checkToolEnabled('logout');
                    if (disabledResponse) return disabledResponse;

                    const { token } = message;

                    try {
                        const logoutResponse = await this.axiosInstance.delete('/logout', {
                            headers: {
                                Authorization: `Bearer ${token}`
                            }
                        });


                        // Loggen des erfolgreichen Logouts
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'logoutSuccess', t.logoutSuccess.replace('${data}', JSON.stringify(logoutResponse.data)), 'info');

                        return {
                            data: {}, // Optional: Zusätzliche Daten könnten hier eingefügt werden
                            status: logoutResponse.data?.status || 'no status', // Dynamisch, falls der API-Status einheitlich ist
                            message: logoutResponse.data?.message || 'no message', // API-Nachricht verwenden oder Standardnachricht
                        };
                    } catch (error) {
                        const logoutErrorMessage = error.response?.data || error.message;
                        // Loggen des Fehlers beim Logout
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'logoutError', t.logoutError.replace('${error}', logoutErrorMessage), 'error');

                        return {
                            data: {},
                            message: error.response?.data || error.message || t.noErrorMessage,
                            status: error.response?.status || 'E11-M-1150', // Internal Server Error oder spezifischer Statuscode
                        };
                    }
                }
                /* 2.0 Chat #######################################################################################*/
                case 'chat': {
                    const disabledResponse = checkToolEnabled('chat');
                    if (disabledResponse) return disabledResponse;

                    // Extrahiere den Token und die Argumente
                    const token = message.token; // Token direkt extrahieren
                    const args = message.arguments || {}; // Sichere Extraktion der Argumente
                    const { question, usePublic, groups, language } = args;

                    // Argument-Validierung
                    if (!args || !args.question) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chat', 'Fehlende Frage in den Argumenten.', 'error');
                        return {
                            status: 'E20-M-2050',
                            message: 'Fehlende Frage in den Argumenten.',
                        };
                    }

                    // Loggen des extrahierten Tokens
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chat', `Extrahierter Token: ${token}`, 'info');

                    // Konflikt zwischen `usePublic` und `groups` lösen
                    if (usePublic && groups && groups.length > 0) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatWarning', t.publicGroupsConflictWarning, 'warn');
                        args.usePublic = false;
                    }

                    try {
                        // API-Aufruf zur Verarbeitung der Chat-Anfrage
                        const response = await this.axiosInstance.post(
                            '/chats',
                            {
                                question,
                                usePublic: usePublic || false,
                                groups: Array.isArray(groups) ? groups : groups ? [groups] : [],
                                language: language || 'de',
                            },
                            {
                                headers: { Authorization: `Bearer ${token}` },
                            }
                        );

                        const data = response.data?.data || {};
                        // Loggen der erfolgreichen Chat-Antwort
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatSuccess', t.chatResponseSuccess.replace('${data}', JSON.stringify(data)), 'info');

                        // Erfolgsantwort mit Status und Daten
                        return {
                            status: response.data?.status || 'ok',
                            message: response.data?.message || 'Chat erfolgreich.',
                            content: {
                                chatId: data.chatId,
                                answer: data.answer,
                                sources: data.sources || [],
                            },
                        };
                    } catch (error) {
                        const chatApiErrorMessage = error.message || error.response?.data;
                        // Loggen des Fehlers bei der Chat-API-Anfrage
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'chatApiError', t.chatApiError.replace('${error}', chatApiErrorMessage), 'error');

                        // Fehlerantwort mit Status und Nachricht
                        return {
                            status: 'E20-M-2051',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 2.1 Continue Chat ##############################################################################*/
                case 'continue_chat': {
                    const disabledResponse = checkToolEnabled('continue_chat');
                    if (disabledResponse) return disabledResponse;

                    const token = message.token; // Token direkt extrahieren
                    const args = message.arguments || {}; // Sichere Extraktion der Argumente
                    const { chatId, question } = args;

                    if (!args || !args.chatId || !args.question) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chat', 'Fehlende erforderliche Parameter: chatId und/oder question.', 'error');
                        return { status: 'E21-M-2150', message: 'Fehlende erforderliche Parameter: chatId und/oder question.' };
                    }

                    try {
                        const continueChatResponse = await this.axiosInstance.patch(
                            `/chats/${chatId}`,
                            { question },
                            { headers: { Authorization: `Bearer ${token}` } }
                        );

                        // Loggen der erfolgreichen Continue-Chat-Antwort
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'continue_chatSuccess', t.conversationSuccess.replace('${data}', JSON.stringify(continueChatResponse.data, null, 2)), 'info');

                        return {
                            content: {
                                chatId: continueChatResponse.data.data.chatId,
                                answer: continueChatResponse.data.data.answer,
                                sources: continueChatResponse.data.sources || [],
                                message: continueChatResponse.data.message,
                                status: continueChatResponse.data.status,
                            },
                        };
                    } catch (error) {
                        // Loggen des Fehlers bei der Continue-Chat-API-Anfrage
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'apiRequestError', t.apiRequestError.replace('${error}', error.message), 'error');
                        return {
                            status: 'E21-M-2151',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 2.2 Get Chat Info ##############################################################################*/
                case 'get_chat_info': {
                    const disabledResponse = checkToolEnabled('get_chat_info');
                    if (disabledResponse) return disabledResponse;

                    const { token } = message; // Token direkt aus `message` extrahieren
                    const args = message.arguments || {}; // Argumente aus `message` extrahieren
                    const { chatId } = args; // chatId aus den Argumenten extrahieren

                    if (!chatId) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_info', 'chatId ist erforderlich, um Chat-Informationen abzurufen.', 'error');
                        return { status: 'E22-M-2250', message: 'chatId ist erforderlich, um Chat-Informationen abzurufen.' };
                    }

                    try {
                        const response = await this.axiosInstance.get(`/chats/${chatId}`, {
                            headers: { Authorization: `Bearer ${token}` }
                        });

                        const chatData = response.data?.data;

                        if (!chatData) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_info', t.noChatData, 'error');
                            return {
                                status: 'E22-M-2251',
                                message: t.noChatData,
                            };
                        }

                        // Formatiertes Ergebnis zurückgeben
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_info', `Chat-Informationen abgerufen: ${JSON.stringify(chatData)}`, 'info');

                        return {
                            data: {
                                chatId: chatData.chatId,
                                title: chatData.title || 'Unbenannter Chat',
                                language: chatData.language || 'Unbekannt',
                                groups: chatData.groups || [],
                                messages: chatData.messages || []
                            },
                            message: response.data?.message || 'Erfolgreich abgerufen.'
                        };
                    } catch (error) {
                        const fetchChatErrorMessage = error.message || error.response?.data;
                        // Loggen des Fehlers beim Abrufen der Chat-Informationen
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_chat_infoError', t.fetchChatInfoError.replace('${error}', fetchChatErrorMessage), 'error');
                        return {
                            status: 'E22-M-2252',
                            message: error.response?.data?.message || unknownError,
                        };
                    }
                }
                /* 3.0 Create Source ##############################################################################*/
                case 'create_source': {
                    const disabledResponse = checkToolEnabled('create_source');
                    if (disabledResponse) return disabledResponse;

                    const args = getArguments(message);
                    const token = message.token;

                    // Validierung: Erforderliche Parameter prüfen
                    if (!token) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_source', 'Token fehlt.', 'error');
                        return { status: 'E30-M-3050', message: t.missingTokenError };
                    }
                    if (!args || !args.name || !args.content) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_source', 'Fehlende erforderliche Parameter: name und content.', 'error');
                        return { status: 'E30-M-3051', message: t.missingParametersError.replace('${parameters}', 'name und content') };
                    }

                    const { name, content, groups } = args;

                    try {
                        // Gruppenvalidierung vorab durchführen
                        if (groups && groups.length > 0) {
                            const groupValidation = await this.validateGroups(groups, token);
                            if (!groupValidation.isValid) {
                                if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_source', `Ungültige Gruppen: ${groupValidation.invalidGroups.join(', ')}`, 'error');
                                return {
                                    status: 'E30-M-3052',
                                    message: t.invalidGroupsError.replace('${invalidGroups}', groupValidation.invalidGroups.join(', '))
                                };
                            }
                        }

                        // API-Aufruf zur Erstellung der Quelle
                        const createSourceResponse = await this.axiosInstance.post(
                            '/sources',
                            { name, content, groups },
                            { headers: { Authorization: `Bearer ${token}` } }
                        );

                        // Loggen der erfolgreichen Erstellung der Quelle
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceSuccess', `Quelle erfolgreich erstellt: ${JSON.stringify(createSourceResponse.data)}`, 'info');

                        // Erfolgsantwort
                        return {
                            status: createSourceResponse.data?.status || 'ok',
                            message: createSourceResponse.data?.message || 'Quelle erfolgreich erstellt.',
                            data: createSourceResponse.data?.data,
                        };
                    } catch (error) {
                        const createSourceError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Erstellung der Quelle
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'create_sourceError', t.createSourceError.replace('${error}', createSourceError), 'error');

                        // Fehlerhafte Antwort
                        if (error.response) {
                            return {
                                status: 'E30-M-3053',
                                message: error.response?.data?.message || error.message || t.noErrorMessage,
                                details: {
                                    status: error.response.status,
                                    headers: error.response.headers,
                                    data: error.response.data,
                                },
                            };
                        } else if (error.request) {
                            return {
                                status: 'E30-M-3054',
                                message: t.noServerResponse,
                                details: { request: error.request },
                            };
                        } else {
                            return {
                                status: 'E30-M-3055',
                                message: error.message || unknownError,
                            };
                        }
                    }
                }
                /* 3.1 Get Source #################################################################################*/
                case 'get_source': {
                    const disabledResponse = checkToolEnabled('get_source');
                    if (disabledResponse) return disabledResponse;
                    const { token, arguments: args } = message; // Extrahiere den Token und die Argumente
                    const { sourceId } = args; // Extrahiere sourceId aus den Argumenten

                    if (!sourceId) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_source', 'sourceId ist erforderlich, um eine Quelle abzurufen.', 'error');
                        return { status: 'E31-M-3150', message: t.groupNameRequired.replace('${param}', 'sourceId') };
                    }

                    // Loggen des Beginns der Quellenanfrage
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_source', t.makingGetSourceRequest.replace('${sourceId}', sourceId), 'info');

                    try {
                        const sourceResponse = await this.axiosInstance.get(`/sources/${sourceId}`, {
                            headers: {
                                Authorization: `Bearer ${token}`, // Nutze den vom Client bereitgestellten Token
                            },
                        });

                        // Loggen der erhaltenen Quellenantwort
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_sourceSuccess', t.gotGetSourceResponse.replace('${data}', JSON.stringify(sourceResponse.data, null, 2)), 'info');

                        return {
                            content: sourceResponse.data,
                        };
                    } catch (error) {
                        // Loggen des Fehlers bei der Quellenanfrage
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'get_sourceError', t.errorHandlingRequest.replace('${error}', error.message || JSON.stringify(error.response?.data, null, 2)), 'error');
                        return {
                            status: 'E31-M-3151',
                            message: t.apiErrorDetails
                                .replace('${status}', error.response?.status || 'E31-M-3151')
                                .replace('${data}', JSON.stringify(error.response?.data || {}, null, 2)),
                        };
                    }
                }
                /* 3.2 List Sources ###############################################################################*/
                case 'list_sources': {
                    const disabledResponse = checkToolEnabled('list_sources');
                    if (disabledResponse) return disabledResponse;
                    const { token, attributes } = message; // Extrahiere den Token und die Attribute

                    if (!attributes || !attributes.groupName) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sources', 'Gruppenname erforderlich für diese Anfrage.', 'error');
                        return { status: 'E32-M-3250', message: 'Gruppenname erforderlich für diese Anfrage.' };
                    }

                    const groupName = attributes.groupName; // Extrahiere den groupName aus attributes

                    // Loggen des Beginns der Quellenliste-Anfrage
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sources', t.fetchingSources.replace('${groupName}', groupName), 'info');

                    try {
                        // Führe die API-Anfrage aus, um die Quellen für die Gruppe zu erhalten
                        const sourceResponse = await this.axiosInstance.post(
                            '/sources/groups',
                            { groupName },
                            {
                                headers: {
                                    Authorization: `Bearer ${token}`, // Nutze den vom Client bereitgestellten Token
                                },
                            }
                        );

                        // Loggen der erhaltenen Quellenliste
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sourcesSuccess', t.sourcesRetrieved.replace('${data}', JSON.stringify(sourceResponse.data, null, 2)), 'info');

                        return {
                            content: sourceResponse.data, // Sende die Antwort zurück
                        };
                    } catch (error) {
                        // Loggen des Fehlers bei der Quellenliste-Anfrage
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_sourcesError', t.groupValidationError.replace('${error}', error.message || JSON.stringify(error.response?.data)), 'error');
                        return {
                            status: 'E32-M-3251',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 3.3 Edit Source ################################################################################*/
                case 'edit_source': {
                    const disabledResponse = checkToolEnabled('edit_source');
                    if (disabledResponse) return disabledResponse;

                    const { token, arguments: args } = message;
                    const { sourceId, title, content, groups } = args;

                    // Validierung: Erforderliche Parameter
                    if (!sourceId) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_source', 'sourceId ist erforderlich, um einen Benutzer zu bearbeiten.', 'error');
                        return {
                            data: {},
                            message: t.missingParameterError.replace('${parameter}', 'sourceId'),
                            status: 'E33-M-3350', // Bad Request
                        };
                    }

                    // Loggen des Beginns der Quellenbearbeitung
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_source', t.editSourceLog.replace('${sourceId}', sourceId).replace('${title}', title || 'unverändert'), 'info');

                    try {
                        // Nur Felder senden, die tatsächlich aktualisiert werden sollen
                        const payload = {};
                        if (title) payload.title = title;
                        if (content) payload.content = content;
                        if (groups) payload.groups = groups;

                        const editSourceResponse = await this.axiosInstance.patch(
                            `/sources/${sourceId}`,
                            payload,
                            {
                                headers: {
                                    Authorization: `Bearer ${token}` // Nutze den bereitgestellten Token
                                },
                            }
                        );

                        // Loggen der erfolgreichen Quellenbearbeitung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_sourceSuccess', t.editSourceSuccess.replace('${data}', JSON.stringify(editSourceResponse.data, null, 2)), 'info');

                        // Erfolgreiche Antwort
                        return {
                            data: editSourceResponse.data?.data || {}, // Optionale Daten aus der API
                            message: editSourceResponse.data?.message || 'Quelle erfolgreich bearbeitet.',
                            status: editSourceResponse.status || 200, // OK
                        };
                    } catch (error) {
                        const editSourceError = error.message || JSON.stringify(error.response?.data);
                        // Loggen des Fehlers bei der Quellenbearbeitung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_sourceError', t.editSourceError.replace('${error}', editSourceError), 'error');

                        // Fehlerhafte Antwort
                        return {
                            data: {},
                            message: error.response?.data?.message || 'Bearbeiten der Quelle fehlgeschlagen. Bitte versuchen Sie es später erneut.',
                            status: error.response?.status || 'E33-M-3351', // Internal Server Error
                        };
                    }
                }
                /* 3.4 Delete Source ##############################################################################*/
                case 'delete_source': {
                    const disabledResponse = checkToolEnabled('delete_source');
                    if (disabledResponse) return disabledResponse;

                    const { token, arguments: args } = message;
                    const { sourceId } = args;

                    if (!sourceId) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_source', 'sourceId ist erforderlich, um eine Quelle zu löschen.', 'error');
                        return { status: 'E34-M-3450', message: t.groupNameRequired.replace('${param}', 'sourceId') };
                    }

                    // Loggen des Beginns der Quellenlöschung
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_source', t.deleteGroupLog.replace('${groupName}', sourceId), 'info');

                    try {
                        const deleteResponse = await this.axiosInstance.delete(`/sources/${sourceId}`, {
                            headers: { Authorization: `Bearer ${token}` },
                        });

                        // Loggen der erfolgreichen Quellenlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_sourceSuccess', t.deleteUserSuccess.replace('${data}', JSON.stringify(deleteResponse.data, null, 2)), 'info');

                        return {
                            content: deleteResponse.data,
                        };
                    } catch (error) {
                        const deleteSourceError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Quellenlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_sourceError', t.deleteSourceError.replace('${error}', deleteSourceError), 'error');

                        return {
                            status: 'E34-M-3451',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 4.0 List Groups ################################################################################*/
                case 'list_groups': {
                    const disabledResponse = checkToolEnabled('list_groups');
                    if (disabledResponse) return disabledResponse;

                    const { token } = message; // Token direkt extrahieren

                    try {
                        await this.ensureAuthenticated(token);

                        const response = await this.axiosInstance.get('/groups');
                        let assignableGroups = response.data?.data?.assignableGroups || [];
                        const personalGroups = response.data?.data?.personalGroups || [];
                        const messageText = response.data?.message || 'no_message'; // Fallback für Nachricht
                        const status = response.data?.status || 'E40-M-4050'; // Fallback für Status

                        if (isRestrictedGroupsEnabled) {
                            // Loggen der Einschränkung bei RESTRICTED_GROUPS
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsWarning', t.restrictedGroupsWarning, 'warn');
                            assignableGroups = ["NO ACCESS ALLOWED BY THE MCP-SERVER CONFIG"]; // Alle assignableGroups entfernen
                        }

                        // Loggen der erfolgreichen Gruppenliste
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsSuccess', `Gruppenliste abgerufen: ${JSON.stringify(response.data)}`, 'info');

                        return {
                            data: {
                                personalGroups,
                                assignableGroups,
                                message: messageText,
                                status,
                            },
                        };
                    } catch (error) {
                        const fetchGroupsError = error.message || JSON.stringify(error.response?.data);
                        // Loggen des Fehlers beim Abrufen der Gruppen
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'list_groupsError', t.fetchGroupsError.replace('${error}', fetchGroupsError), 'error');

                        // Detaillierte Fehlerbehandlung
                        if (axios.isAxiosError(error)) {
                            const status = error.response?.status;
                            const serverMessage = error.response?.data?.message || error.message || 'no error message';
                            return {
                                status: 'E40-M-4051',
                                message: `Fehler beim Abrufen der Gruppen: ${serverMessage} (Status: ${status})`,
                            };
                        }

                        return {
                            status: 'E40-M-4052',
                            message: unknownError,
                        };
                    }
                }
                /* 4.1 Store Group ################################################################################*/
                case 'store_group': {
                    const disabledResponse = checkToolEnabled('store_group');
                    if (disabledResponse) return disabledResponse;

                    const { groupName, description } = message.arguments; // Extrahiere die Argumente
                    const clientToken = message.token; // Token aus der Anfrage

                    if (!groupName || !description) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_group', t.missingGroupNameAndDesc, 'error');
                        return { 
                          status: 'E41-M-4150', 
                          message: t.missingGroupNameAndDesc 
                        };
                    }

                    if (!clientToken) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_group', 'Token fehlt.', 'error');
                        return { status: 'E41-M-4151', message: t.missingTokenError };
                    }

                    try {
                        // API-Aufruf mit dem vom Client bereitgestellten Token
                        const createGroupResponse = await this.axiosInstance.post(
                            '/groups',
                            { groupName, description },
                            {
                                headers: {
                                    Authorization: `Bearer ${clientToken}` // Nutze nur den Client-Token
                                }
                            }
                        );

                        // Loggen der erfolgreichen Gruppenerstellung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupSuccess', t.createGroupSuccess.replace('${data}', JSON.stringify(createGroupResponse.data)), 'info');

                        return {
                            content: createGroupResponse.data,
                        };
                    } catch (error) {
                        const apiError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Gruppenerstellung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_groupError', t.apiRequestError.replace('${error}', apiError), 'error');

                        return {
                            status: 'E41-M-4152',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 4.2 Delete Group ###############################################################################*/
                case 'delete_group': {
                    const disabledResponse = checkToolEnabled('delete_group');
                    if (disabledResponse) return disabledResponse;

                    const { token, arguments: args } = message; // Extrahiere Token und Argumente
                    const { groupName } = args;

                    if (!groupName) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_group', t.missingGroupNameParam, 'error');
                        return { 
                          status: 'E42-M-4250', 
                          message: t.missingGroupNameParam 
                        };
                    }

                    // Loggen des Beginns der Gruppenlöschung
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_group', t.deleteGroupLog.replace('${groupName}', groupName), 'info');

                    try {
                        // API-Aufruf mit dem Token des Clients
                        const deleteGroupResponse = await this.axiosInstance.delete('/groups', {
                            data: { groupName }, // JSON-Body für DELETE-Request
                            headers: {
                                Authorization: `Bearer ${token}` // Nutze den vom Client bereitgestellten Token
                            },
                        });

                        // Loggen der erfolgreichen Gruppenlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupSuccess', t.deleteGroupSuccessLog.replace('${data}', JSON.stringify(deleteGroupResponse.data)), 'info');

                        return {
                            data: deleteGroupResponse.data?.data || {},
                            message: deleteGroupResponse.data?.message || 'success',
                            status: deleteGroupResponse.status || 200,
                        };
                    } catch (error) {
                        const deleteSourceError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Gruppenlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_groupError', t.deleteSourceError.replace('${error}', deleteSourceError), 'error');

                        return {
                            status: 'E42-M-4251',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 5.0 Store User #################################################################################*/
                case 'store_user': {
                    const disabledResponse = checkToolEnabled('store_user');
                    if (disabledResponse) return disabledResponse;
                    const { token, arguments: args } = message;

                    // Validierung der erforderlichen Parameter
                    if (!args || !args.name || !args.email || !args.password) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_user', 'Fehlende erforderliche Parameter: name, email oder password.', 'error');
                        return { status: 'E50-M-5050', message: 'Fehlende erforderliche Parameter: name, email oder password.' };
                    }

                    const Pwd = args.password;

                    // Überprüfe, ob das Passwort vorhanden ist
                    if (!Pwd) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_user', t.passwordIsRequired, 'error');
                        return {
                            status: 'E10-M-1050',
                            message: t.passwordIsRequired
                        };
                    }

                    let password;

                    // Passwort entschlüsseln, falls erforderlich
                    if (typeof PwEncryption !== 'undefined' && PwEncryption) {
                        password = decryptPassword(Pwd);
                    } else {
                        password = Pwd;
                    }

                    try {
                        // Payload für die API-Anfrage
                        const payload = {
                            name: args.name,
                            email: args.email,
                            language: args.language || 'en',
                            timezone: args.timezone || 'Europe/Berlin',
                            password: password,
                            usePublic: args.usePublic || false,
                            groups: args.groups || [],
                            roles: args.roles || [],
                            activateFtp: args.activateFtp || false,
                            ftpPassword: args.ftpPassword || '',
                        };

                        // Loggen des Payloads vor der API-Anfrage
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_user', t.createUserLog.replace('${payload}', JSON.stringify(payload)), 'info');

                        // API-Aufruf
                        const createUserResponse = await this.axiosInstance.post('/users', payload, {
                            headers: {
                                Authorization: `Bearer ${token}`
                            }
                        });

                        // Loggen der erfolgreichen Benutzererstellung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_userSuccess', t.createUserSuccess.replace('${data}', JSON.stringify(createUserResponse.data)), 'info');

                        return {
                            content: createUserResponse.data,
                        };
                    } catch (error) {
                        const createUserError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Benutzererstellung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'store_userError', t.createUserError.replace('${error}', error.response?.data || error.message), 'error');

                        const errors = error.response?.data?.errors;
                        if (errors) {
                            const errorMessages = [];
                            for (const [key, messages] of Object.entries(errors)) {
                                messages.forEach(message => errorMessages.push(`${key}: ${message}`));
                            }

                            return {
                                status: 'E50-M-5051',
                                message: 'Fehler beim Erstellen des Benutzers:',
                                errors: errorMessages
                            };
                        }

                        return {
                            status: 'E50-M-5052',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 5.1 Edit User ##################################################################################*/
                case 'edit_user': {
                    const disabledResponse = checkToolEnabled('edit_user');
                    if (disabledResponse) return disabledResponse;

                    const { token, arguments: args } = message;
                    const tokenValidation = validateToken(token);
                    if (tokenValidation) return tokenValidation;

                    // Mindestens die E-Mail muss angegeben sein, um den User zu identifizieren
                    if (!args || !args.email) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_user', t.emailRequiredForEdit, 'error');
                        return {
                            status: 'E51-R-5100',
                            message: t.emailRequiredForEdit
                        };
                    }
                    let password = null;

                    if (args.password) {
                        const Pwd = args.password;
                        if (!Pwd) {
                            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_user', 'Passwort ist erforderlich.', 'error');
                            return {
                                status: 'E51-M-1050',
                                message: 'Passwort ist erforderlich.',
                            };
                        }
                        if (typeof PwEncryption !== 'undefined' && PwEncryption) {
                            password = decryptPassword(Pwd);
                        } else {
                            password = Pwd;
                        }
                    }

                    try {
                        // Nur Felder senden, die tatsächlich aktualisiert werden sollen
                        const payload = {};
                        if (args.name) payload.name = args.name;
                        if (args.password) payload.password = password;
                        if (args.language) payload.language = args.language;
                        if (args.timezone) payload.timezone = args.timezone;
                        if (Array.isArray(args.roles)) payload.roles = args.roles;
                        if (Array.isArray(args.groups)) payload.groups = args.groups;
                        if (typeof args.usePublic === 'boolean') payload.usePublic = args.usePublic;

                        // E-Mail ist Pflicht, um den Benutzer auf dem Server zu finden
                        payload.email = args.email;
                        const response = await this.axiosInstance.patch(
                            '/users',
                            payload,
                            {
                                headers: { Authorization: `Bearer ${token}` }
                            }
                        );

                        // Loggen der erfolgreichen Benutzerbearbeitung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userSuccess', t.editUserSuccess.replace('${data}', JSON.stringify(response.data)), 'info');

                        return {
                            status: response.data?.status || 'ok',
                            message: response.data?.message || 'Benutzer erfolgreich bearbeitet.',
                            data: response.data?.data
                        };
                    } catch (error) {
                        const editUserError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Benutzerbearbeitung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'edit_userError', t.editUserError.replace('${error}', editUserError), 'error');
                        return {
                            status: error.response?.status || 'E51-M-5151',
                            message: error.response?.data?.message || 'Fehler beim Bearbeiten des Benutzers.'
                        };
                    }
                }
                /* 5.2 Delete User ################################################################################*/
                case 'delete_user': {
                    const disabledResponse = checkToolEnabled('delete_user');
                    if (disabledResponse) return disabledResponse;
                    const { token, arguments: args } = message;

                    const { email } = args;

                    if (!email) {
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_user', 'Email ist erforderlich, um einen Benutzer zu löschen.', 'error');
                        return { status: 'E52-M-5250', message: 'Email ist erforderlich, um einen Benutzer zu löschen.' };
                    }

                    // Loggen des Beginns der Benutzerlöschung
                    if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_user', t.deleteGroupLog.replace('${groupName}', email), 'info');

                    try {
                        const response = await this.axiosInstance.delete(
                            '/users',
                            {
                                data: { email },
                                headers: { Authorization: `Bearer ${token}` },
                            }
                        );

                        // Loggen der erfolgreichen Benutzerlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_userSuccess', t.deleteUserSuccess.replace('${data}', JSON.stringify(response.data, null, 2)), 'info');

                        return {
                            content: response.data,
                        };
                    } catch (error) {
                        const deleteUserError = error.response?.data || error.message;
                        // Loggen des Fehlers bei der Benutzerlöschung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'delete_userError', t.deleteUserError.replace('${error}', deleteUserError), 'error');
                        return {
                            status: 'E52-M-5251',
                            message: error.response?.data?.message || error.message || t.noErrorMessage,
                        };
                    }
                }
                /* 9.0 Generate Key ###############################################################################*/
                case 'keygen': {
                    const disabledResponse = checkToolEnabled('keygen');
                    if (disabledResponse) return disabledResponse;

                    const { password } = message.arguments;

                    try {
                        // Passwort verschlüsseln
                        const encryptedPassword = getEncryptedKey(password);

                        // Loggen der erfolgreichen Key-Generierung
                        if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'keygen', t.keygenSuccess, 'info');


                        // Schlüssel zurückgeben
                        return {
                            data: {
                                key: encryptedPassword
                            },
                            status: 'ok',
                            message: 'Keygen erfolgreich.',
                        };
                    } catch (error) {
                        // Loggen des Fehlers bei der Key-Generierung
                        if (!isanonymousModeEnabled) logEvent(
                            'system', 'N/A', 'keygenError',
                            t.keygenErrorPrefix + ' ' + error.message,
                            'error'
                        );
                        return {
                            data: {},
                            message: error.message || 'Keygen fehlgeschlagen.',
                            status: 'E90-M-1150',
                        };
                    }
                }
                default: {
                    // Loggen unbekannter Befehle
                    if (!isanonymousModeEnabled) logEvent(
                        'system', 'N/A', 'unknownCommand',
                        t.unknownCommandError.replace('${cmd}', message.command),
                        'warn'
                    )
                    return { status: 'E99-M-9950', message: 'Unbekannter Befehl.' };
                }
            }

        } catch (err) {
            // Loggen des Fehlers im Haupt-Handler
            if (!isanonymousModeEnabled) logEvent('system', 'N/A', 'tcpServerError', `${t.tcpServerError} ${err.message || JSON.stringify(err, null, 2)}`, 'error');
            return { status: 'E52-M-5252', message: err.message || t.internalServerError };
            }
        });
    }
}
const server = new PrivateGPTServer();

// Log-Viewer Webserver konfigurieren
const app = express();
const httpServer = createHttpServer(app);
const io = new SocketIoServer(httpServer);
// const stripAnsi = (text) => {
    // return text.replace(/\x1b\[[0-9;]*m/g, '');
// };


const LOG_FILE_PATH = path.join(__dirname, '../logs/server.log'); // Pfad zu Ihrer Logdatei

// Statische Dateien bereitstellen (optional, falls eine HTML-Oberfläche benötigt wird)
app.use(express.static(path.join(__dirname, 'public')));

// WebSocket-Verbindung für Logs
io.on('connection', (socket) => {
    if (!isanonymousModeEnabled) logEvent(
        'server',
        'websocket',
        'clientConnected',
        messages[lang].clientConnected,
        'info'
    );
    sendLogContent(socket);

    socket.on('disconnect', () => {
        if (!isanonymousModeEnabled) logEvent(
            'server',
            'websocket',
            'clientDisconnected',
            messages[lang].clientDisconnected,
            'info'
        );
    });
});

// Funktion, um den Loginhalt an einen Client zu senden
const sendLogContent = async (socket) => {
    try {
        let data = await fs.promises.readFile(LOG_FILE_PATH, 'utf8');
        data = stripAnsi(data); // nutzt jetzt den Import
        socket.emit('logUpdate', data);
    } catch (err) {
            if (!isanonymousModeEnabled) logEvent(
            'server',
            'filesystem',
            'logReadError',
            messages[lang].logReadError.replace('${error}', err.message),
            'error'
        );
    }
};
/*
const sendLogContent = async (socket) => {
    try {
        let data = await fs.promises.readFile(LOG_FILE_PATH, 'utf8');
        data = stripAnsi(data); // ANSI-Farben entfernen
        socket.emit('logUpdate', data);
    } catch (err) {
        if (!isanonymousModeEnabled) logEvent(
            'server',
            'filesystem',
            'logReadError',
            messages[lang].logReadError.replace('${error}', err.message),
            'error'
        );
    }
};*/

// Überwachung der Logdatei auf Änderungen
chokidar.watch(LOG_FILE_PATH).on('change', async () => {
    try {
        const data = await fs.promises.readFile(LOG_FILE_PATH, 'utf8');
        io.sockets.emit('logUpdate', data);
    } catch (err) {
        if (!isanonymousModeEnabled) logEvent(
            'server',
            'filesystem',
            'logChangeError',
            messages[lang].logChangeError.replace('${error}', err.message),
            'error'
        );
    }
});

// Log-Viewer HTTP-Server starten
const WEB_PORT = 3000;
httpServer.listen(WEB_PORT, () => {
    if (!isanonymousModeEnabled) logEvent(
        'server',
        'web',
        'logViewerRunning',
        messages[lang].logViewerRunning.replace('${port}', WEB_PORT),
        'info'
    );
});

// Server läuft
server.run().catch(error => {
    if (!isanonymousModeEnabled) logEvent(
        'server',
        'N/A',
        'serverError',
        messages[lang].serverError.replace('${error}', error.message),
        'error'
    );
});

displayStartHeader();
// Server läuft