# Custom Validators
FastAPI Assets allows you to create custom validators by extending the base validator classes. This enables you to implement specific validation logic tailored to your application's needs. You can also create custom validation functions to be used with existing validators. Let's explore how to create and use custom validators.

### Creating a Custom File Validator

To create a custom file validator, you can subclass the `FileValidator` and override the `validate` method to include your custom logic. Here's an example of a custom file validator that checks for a specific filename pattern:

```python
import re
from fastapi_assets.validators import FileValidator
class CustomFileValidator(FileValidator):
    def __init__(self, filename_pattern: str, **kwargs):
        super().__init__(**kwargs)
        self.filename_pattern = re.compile(filename_pattern)

    async def validate(self, file):
        await super().validate(file)  # Perform standard validations
        if not self.filename_pattern.match(file.filename):
            raise ValueError(f"Filename '{file.filename}' does not match the required pattern.")
```

You can then use this custom validator in your FastAPI routes:

```python
from fastapi import FastAPI, UploadFile, Depends
app = FastAPI()
custom_validator = CustomFileValidator(
    filename_pattern=r"^[\w\s-]+\.(jpg|jpeg|png|gif)$",
    max_size="5MB",
    content_types=["image/jpeg", "image/png", "image/gif"]
)
@app.post("/upload/custom/")
async def upload_custom_file(file: UploadFile = Depends(custom_validator)):
    return {"filename": file.filename, "size": file.size}
```
### Creating a Custom Validation Function
You can also create custom validation functions that can be passed to existing validators. For example, let's create a custom function to validate that a file's size is an exact multiple of 1024 bytes:

```python
from fastapi_assets.validators import FileValidator
from fastapi_assets.core import ValidationError
def exact_multiple_of_1024(file):
    if file.size % 1024 != 0:
        raise ValidationError("File size must be an exact multiple of 1024 bytes.")
file_validator = FileValidator(
    max_size="10MB",
    content_types=["application/octet-stream"],
    validators=[exact_multiple_of_1024]
)
```

You can then use this validator in your FastAPI routes:

```python
from fastapi import FastAPI, UploadFile, Depends
app = FastAPI()
@app.post("/upload/exact-multiple/")
async def upload_exact_multiple_file(file: UploadFile = Depends(file_validator)):
    return {"filename": file.filename, "size": file.size}
```

### Summary
Creating custom validators in FastAPI Assets allows you to implement specific validation logic that suits your application's requirements. By subclassing existing validators or creating custom validation functions, you can enhance the validation capabilities of your FastAPI applications.

## Contributing to FastAPI Assets
Thank you for your interest in contributing to FastAPI Assets! We welcome contributions from the community to help improve and expand this project. Whether you're fixing bugs, adding new features, or improving documentation, your contributions are valuable.
