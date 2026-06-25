from app.schemas.generated_test import GeneratedTestArtifact

class Formatter:
    """Normalizes the generated code before it's written to disk."""
    
    def format(self, artifact: GeneratedTestArtifact) -> GeneratedTestArtifact:
        for gen_file in artifact.generated_files:
            # Strip trailing whitespaces and normalize line endings
            content = gen_file.content
            lines = content.split('\n')
            formatted_lines = [line.rstrip() for line in lines]
            
            # Ensure file ends with a single newline
            while formatted_lines and formatted_lines[-1] == "":
                formatted_lines.pop()
            formatted_lines.append("")
            
            gen_file.content = "\n".join(formatted_lines)
            
        return artifact
