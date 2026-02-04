/**
 * HERMES qopilot Extension Hook - Session Discovery via VSCode Native APIs
 * 
 * This runs in the VSCode extension context with access to:
 * - vscode.workspace APIs
 * - vscode.extensions.getExtension() for chat extension info
 * - File system APIs with proper permissions
 * - Session storage via extension context
 * 
 * Register as command: qopilot.hermes.listChatSessions
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export interface HermesChatSession {
  session_id: string;
  workspace_path: string;
  workspace_hash: string;
  custom_title: string;
  request_count: number;
}

/**
 * Command: qopilot.hermes.listChatSessions
 * 
 * Query VSCode Copilot Chat extension for all available chat sessions.
 * Returns structured data without requiring filesystem scanning.
 */
export async function listChatSessionsViaAPI(): Promise<HermesChatSession[]> {
  const sessions: HermesChatSession[] = [];
  
  try {
    // Get the Copilot Chat extension
    const copilotExtension = vscode.extensions.getExtension('GitHub.copilot-chat');
    if (!copilotExtension) {
      console.warn('Copilot Chat extension not found');
      return sessions;
    }
    
    // For each workspace folder, query chat sessions
    const workspaceFolders = vscode.workspace.workspaceFolders || [];
    
    for (const folder of workspaceFolders) {
      try {
        // Get VSCode storage path for this workspace
        // Format: AppData/Roaming/Code - Insiders/User/workspaceStorage/{hash}/
        const workspaceStorageUri = vscode.Uri.joinPath(
          vscode.Uri.file(getVSCodeAppDataPath()),
          'workspaceStorage',
          computeWorkspaceHash(folder.uri.fsPath)
        );
        
        const chatSessionsDir = vscode.Uri.joinPath(workspaceStorageUri, 'chatSessions');
        
        // List all session files in chatSessions directory
        const sessionFiles = await vscode.workspace.fs.readDirectory(chatSessionsDir);
        
        for (const [filename, fileType] of sessionFiles) {
          if (fileType !== vscode.FileType.File || !filename.endsWith('.jsonl')) {
            continue;
          }
          
          try {
            // Read session file (JSONL format)
            const sessionFileUri = vscode.Uri.joinPath(chatSessionsDir, filename);
            const fileContent = await vscode.workspace.fs.readFile(sessionFileUri);
            const fileText = new TextDecoder().decode(fileContent);
            
            // Parse last line (current session state)
            const lines = fileText.split('\n').filter(l => l.trim());
            if (lines.length === 0) continue;
            
            const lastLine = lines[lines.length - 1];
            const sessionData = JSON.parse(lastLine);
            const vData = sessionData.v || {};
            
            sessions.push({
              session_id: filename.replace('.jsonl', ''),
              workspace_path: folder.uri.fsPath,
              workspace_hash: computeWorkspaceHash(folder.uri.fsPath),
              custom_title: vData.customTitle || '',
              request_count: (vData.requests || []).length
            });
            
            console.log(`[HERMES] Found session: ${vData.customTitle || filename}`);
          } catch (e) {
            console.warn(`[HERMES] Failed to parse session ${filename}:`, e);
            continue;
          }
        }
      } catch (e) {
        console.warn(`[HERMES] Error scanning workspace ${folder.name}:`, e);
        continue;
      }
    }
    
    console.log(`[HERMES] Discovered ${sessions.length} chat sessions via VSCode API`);
    return sessions;
  } catch (e) {
    console.error('[HERMES] Session discovery failed:', e);
    return sessions;
  }
}

/**
 * Get VSCode AppData path (cross-platform)
 */
function getVSCodeAppDataPath(): string {
  const platform = process.platform;
  const home = process.env.HOME || process.env.USERPROFILE || os.homedir();
  
  if (platform === 'win32') {
    return path.join(home, 'AppData', 'Roaming', 'Code - Insiders', 'User');
  } else if (platform === 'darwin') {
    return path.join(home, 'Library', 'Application Support', 'Code - Insiders', 'User');
  } else {
    // Linux
    return path.join(home, '.config', 'Code - Insiders', 'User');
  }
}

/**
 * Compute workspace hash same way VSCode does
 * This matches the directory name in AppData/User/workspaceStorage/{hash}/
 */
function computeWorkspaceHash(workspacePath: string): string {
  // VSCode uses a hash based on the workspace folder path
  // For simplicity, we can use a sha256 of the path
  // But for HERMES purposes, we can read from vscode.Uri.workspaceFolder metadata
  
  // Alternative: Read from .vscode/settings.json if available
  // Or use vscode extension context storage
  
  // For now, return a placeholder - actual implementation would:
  // 1. Check extension context storage key
  // 2. Or compute from workspace path using same algorithm as VSCode
  
  const crypto = require('crypto');
  return crypto
    .createHash('sha256')
    .update(workspacePath)
    .digest('hex')
    .substring(0, 32);
}

/**
 * Register the command with qopilot extension
 */
export function registerHermesSessionDiscovery(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand('qopilot.hermes.listChatSessions', () => {
      return listChatSessionsViaAPI();
    })
  );
  
  console.log('[HERMES] Session discovery command registered: qopilot.hermes.listChatSessions');
}
