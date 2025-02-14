import * as ts from 'typescript';
import * as path from 'path';
import { promises as fs } from 'fs';

// Represents either a documentation block or code block
interface DocBlock {
    type: 'markdown' | 'code';
    content: string;
    language?: string;
    title?: string;
}

async function processTypeScriptFile(filePath: string): Promise<DocBlock[]> {
    const source = await fs.readFile(filePath, 'utf-8');
    const sourceFile = ts.createSourceFile(
        filePath,
        source,
        ts.ScriptTarget.Latest,
        true
    );
    
    const blocks: DocBlock[] = [];
    let currentMarkdown = '';
    
    // Helper function to process JSDoc comments
    function processJSDocComments(node: ts.Node) {
        const jsDocComments = ((node as any).jsDoc || []) as ts.JSDoc[];
        jsDocComments.forEach(jsDoc => {
            if (jsDoc.comment) {
                currentMarkdown += jsDoc.comment + '\n';
            }
        });
    }
    
    // Walk through each node in the TypeScript file
    function visit(node: ts.Node) {
        // Skip nodes that are children of function declarations, class declarations, etc.
        if (node.parent && (
            ts.isFunctionDeclaration(node.parent) ||
            ts.isClassDeclaration(node.parent) ||
            ts.isMethodDeclaration(node.parent) ||
            ts.isBlock(node.parent)
        )) {
            return;
        }

        processJSDocComments(node);
        
        // Add markdown block if we have accumulated any
        if (currentMarkdown) {
            blocks.push({
                type: 'markdown',
                content: currentMarkdown.trim()
            });
            currentMarkdown = '';
        }
        
        // Add code blocks for top-level declarations only
        if (ts.isFunctionDeclaration(node) || 
            ts.isClassDeclaration(node) || 
            ts.isInterfaceDeclaration(node) ||
            ts.isVariableStatement(node) ||
            ts.isFunctionExpression(node) ||
            ts.isArrowFunction(node)) {
            blocks.push({
                type: 'code',
                language: 'typescript',
                content: node.getText(sourceFile),
                title: path.basename(filePath)
            });
        }
        
        ts.forEachChild(node, visit);
    }
    
    visit(sourceFile);
    
    // Add any remaining markdown
    if (currentMarkdown.trim()) {
        blocks.push({
            type: 'markdown',
            content: currentMarkdown.trim()
        });
    }
    
    return blocks;
}

function generateMarkdown(blocks: DocBlock[]): string {
    // Convert the blocks into markdown format
    return blocks
        .map(block => {
            if (block.type === 'markdown') {
                return block.content;
            } else {
                // Format code blocks with typescript syntax highlighting
                return [
                    '```typescript',
                    block.content,
                    '```'
                ].join('\n');
            }
        })
        .join('\n\n');
}

async function main() {
    // Define input/output directories
    const inputDir = path.join(__dirname, '..', 'ts-examples');
    const outputDir = path.join(__dirname, '..', '..', '..', 'docs', 'reference', 'generated_typescript_docs');
    
    // Create output directory if it doesn't exist
    await fs.mkdir(outputDir, { recursive: true });
    
    // Get all .ts files (not just .lit.ts)
    const files = await fs.readdir(inputDir);
    const tsFiles = files.filter(f => f.endsWith('.ts'));
    
    // Process each file
    for (const file of tsFiles) {
        const inputPath = path.join(inputDir, file);
        const outputPath = path.join(
            outputDir, 
            file.replace('.ts', '.md')
        );

        // Convert the file from .ts to .md
        const blocks = await processTypeScriptFile(inputPath);
        const markdown = await generateMarkdown(blocks);
        await fs.writeFile(outputPath, markdown);
        console.log(`Generated documentation for ${file}`);
    }
}

main();
