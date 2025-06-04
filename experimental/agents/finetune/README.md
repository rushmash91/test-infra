# ACK Fine-Tuning Dataset Generators

This directory contains tools for generating Claude 3 Haiku fine-tuning datasets for AWS Controllers for Kubernetes (ACK) that are compliant with Amazon Bedrock requirements.

## 🎯 **Core Components**

### **1. Ultra-Compact Generator** (`ultra_compact_generator.py`)
- **Purpose**: Creates Bedrock-compliant datasets that fit within 32K token limit
- **Approach**: Ultra-compressed AWS API representations (3 operations per resource max)
- **Format**: Claude 3 Haiku single-turn conversations
- **Token Limit**: ✅ Stays under 32,000 tokens per example
- **Validation**: ✅ Passes full Bedrock validation

```bash
# Generate ultra-compact dataset for all services  
uv run ultra_compact_generator.py --max-services 50 --output bedrock_compliant.jsonl

# Generate for specific services
uv run ultra_compact_generator.py --services s3 lambda dynamodb --output custom.jsonl
```

### **2. Full-Model Generator** (`full_model_haiku_generator.py`)  
- **Purpose**: Uses complete AWS SDK model.json (entire file, not trimmed)
- **Approach**: Whole model context + resource name as input
- **Format**: Claude 3 Haiku single-turn conversations
- **Token Limit**: ⚠️ May exceed 32K tokens (use for other fine-tuning platforms)
- **Use Case**: Maximum context for comprehensive training

```bash
# Generate full-model dataset for all services
uv run full_model_haiku_generator.py --all-services --output full_model_dataset.jsonl

# Generate for specific services  
uv run full_model_haiku_generator.py --services s3 --output full_model_s3.jsonl
```

### **3. New Resource Prompt Generator** (`new_resource_prompt_generator.py`)
- **Purpose**: Generate prompts for AWS resources that don't exist in ACK yet
- **Approach**: Extract AWS SDK model data for any resource and create prompts
- **Format**: Multiple formats (standard, comprehensive, ultra-compact, conversation)
- **Use Case**: Explore new resources and generate training prompts for LLMs

```bash
# Generate standard prompt for API Gateway UsagePlan
uv run new_resource_prompt_generator.py apigateway UsagePlan

# Generate comprehensive analysis with all operations
uv run new_resource_prompt_generator.py apigateway UsagePlan --format comprehensive

# Generate ultra-compact prompt for fine-tuning
uv run new_resource_prompt_generator.py apigateway UsagePlan --format ultra-compact

# Generate Claude Haiku conversation format
uv run new_resource_prompt_generator.py apigateway UsagePlan --conversation --output usageplan.json

# Example: Explore S3 MultiRegionAccessPoint
uv run new_resource_prompt_generator.py s3 MultiRegionAccessPoint --format comprehensive

# Example: Lambda EventSourceMapping
uv run new_resource_prompt_generator.py lambda EventSourceMapping --format standard
```

### **4. Bedrock Validator** (`bedrock_validation.py`)
- **Purpose**: Validates datasets against Amazon Bedrock requirements
- **Checks**: Token limits, format, line counts, file size, reserved keywords
- **Supports**: Both training and validation file validation

```bash
# Validate training dataset
uv run bedrock_validation.py training_dataset.jsonl

# Validate both training and validation datasets
uv run bedrock_validation.py training.jsonl validation.jsonl
```

## 📊 **Dataset Formats**

Both generators create Claude 3 Haiku single-turn conversation format:

```json
{
  "system": "You are an AWS ACK generator for {service}. Generate YAML configurations from AWS API definitions.",
  "messages": [
    {
      "role": "user", 
      "content": "Generate ACK generator.yaml for {Resource} resource in {service}:\n\nAWS API: {...}\n\nGenerate generator.yaml for {Resource}:"
    },
    {
      "role": "assistant",
      "content": "{actual_generator_yaml_config}"
    }
  ]
}
```

## 🔍 **New Resource Examples**

### **API Gateway UsagePlan - Standard Format:**
```bash
uv run new_resource_prompt_generator.py apigateway UsagePlan --format standard
```

**Output:**
```markdown
## AWS Apigateway UsagePlan Resource

### Key Operations:
**CreateUsagePlan** (Create)
- Inputs: name, description, apiStages
- Outputs: id, name, description

**DeleteUsagePlan** (Delete)
- Inputs: usagePlanId

**GetUsagePlan** (Read)
- Inputs: usagePlanId
- Outputs: id, name, description

**UpdateUsagePlan** (Update)
- Inputs: usagePlanId, patchOperations
- Outputs: id, name, description

### Task:
Generate an ACK generator.yaml configuration for the UsagePlan resource in apigateway.

Focus on:
- Resource identification and primary keys
- CRUD operation mappings
- Field configurations (required, immutable, read-only)
- Error handling
- Any service-specific considerations

Generate generator.yaml for UsagePlan:
```

### **S3 MultiRegionAccessPoint - Comprehensive Format:**
```bash
uv run new_resource_prompt_generator.py s3 MultiRegionAccessPoint --format comprehensive
```

This would generate a detailed analysis including all operations, input/output fields, errors, and comprehensive guidance for implementing the resource in ACK.

### **Lambda EventSourceMapping - Ultra-Compact Format:**
```bash
uv run new_resource_prompt_generator.py lambda EventSourceMapping --format ultra-compact
```

This would generate a Bedrock-compliant ultra-compact prompt suitable for fine-tuning within token limits.

### **🎯 Real Ultra-Compact Single-Turn Example:**

Here's the actual Claude 3 Haiku single-turn conversation format from the dataset:

```json
{
  "system": "You are an AWS ACK generator for acm. Generate YAML configurations from compact AWS API definitions.",
  "messages": [
    {
      "role": "user",
      "content": "Generate ACK generator.yaml for Certificate resource in acm:\n\nAWS API: {\n \"service\": {\n  \"name\": \"certificatemanager\",\n  \"protocol\": \"json\"\n },\n \"resource\": \"Certificate\",\n \"operations\": [\n  {\n   \"name\": \"DeleteCertificate\",\n   \"type\": \"Delete\",\n   \"input\": {\n    \"target\": \"com.amazonaws.acm#DeleteCertificateRequest\",\n    \"type\": \"structure\",\n    \"members\": {\n     \"CertificateArn\": {\n      \"type\": \"Arn\"\n     }\n    }\n   },\n   \"output\": {\n    \"target\": \"smithy.api#Unit\"\n   }\n  },\n  {\n   \"name\": \"DescribeCertificate\",\n   \"type\": \"Read\",\n   \"input\": {\n    \"target\": \"com.amazonaws.acm#DescribeCertificateRequest\",\n    \"type\": \"structure\",\n    \"members\": {\n     \"CertificateArn\": {\n      \"type\": \"Arn\"\n     }\n    }\n   },\n   \"output\": {\n    \"target\": \"com.amazonaws.acm#DescribeCertificateResponse\",\n    \"type\": \"structure\",\n    \"members\": {\n     \"Certificate\": {\n      \"type\": \"CertificateDetail\"\n     }\n    }\n   }\n  },\n  {\n   \"name\": \"GetCertificate\",\n   \"type\": \"Read\",\n   \"input\": {\n    \"target\": \"com.amazonaws.acm#GetCertificateRequest\",\n    \"type\": \"structure\",\n    \"members\": {\n     \"CertificateArn\": {\n      \"type\": \"Arn\"\n     }\n    }\n   },\n   \"output\": {\n    \"target\": \"com.amazonaws.acm#GetCertificateResponse\",\n    \"type\": \"structure\",\n    \"members\": {\n     \"Certificate\": {\n      \"type\": \"CertificateBody\"\n     },\n     \"CertificateChain\": {\n      \"type\": \"CertificateChain\"\n     }\n    }\n   }\n  }\n ],\n \"note\": \"Ultra-compact representation for Bedrock fine-tuning\"\n}\n\nGenerate generator.yaml for Certificate:"
    },
    {
      "role": "assistant", 
      "content": "Certificate:\n  hooks:\n    sdk_update_pre_build_request:\n      template_path: hooks/certificate/sdk_update_pre_build_request.go.tpl\n    sdk_create_pre_build_request:\n      template_path: hooks/certificate/sdk_create_pre_build_request.go.tpl\n    sdk_create_post_build_request:\n      code: input.ValidationMethod = \"DNS\"\n    sdk_read_one_pre_set_output:\n      template_path: hooks/certificate/sdk_read_one_pre_set_output.go.tpl\n    sdk_file_end:\n      template_path: hooks/certificate/sdk_file_end.go.tpl\n    late_initialize_post_read_one:\n      template_path: hooks/certificate/late_initialize_post_read_one.go.tpl\n  exceptions:\n    errors:\n      404:\n        code: ResourceNotFoundException\n    terminal_codes:\n    - InvalidParameterException\n    - InvalidDomainValidationOptionsException\n    - InvalidTagException\n    - TagPolicyException\n    - TooManyTagsException\n    - InvalidArnException\n  reconcile:\n    requeue_on_success_seconds: 60\n  fields:\n    DomainName:\n      is_primary_key: false\n      is_required: false\n    Certificate:\n      type: bytes\n      is_secret: true\n      is_immutable: true\n      compare:\n        is_ignored: true\n    PrivateKey:\n      type: bytes\n      is_secret: true\n      is_immutable: true\n      compare:\n        is_ignored: true\n    CertificateArn:\n      type: string\n      is_immutable: true\n    CertificateChain:\n      type: bytes\n      is_immutable: true\n      is_secret: true\n      compare:\n        is_ignored: true\n    CertificateAuthorityARN:\n      references:\n        service_name: acmpca\n        resource: CertificateAuthority\n        path: Status.ACKResourceMetadata.ARN\n      is_immutable: true\n    KeyAlgorithm:\n      late_initialize: {}\n      is_immutable: true\n      compare:\n        is_ignored: true\n    Options:\n      late_initialize: {}\n    CreatedAt:\n      is_read_only: true\n      from:\n        operation: DescribeCertificate\n        path: Certificate.CreatedAt\n    DomainValidations:\n      is_read_only: true\n      from:\n        operation: DescribeCertificate\n        path: Certificate.DomainValidationOptions\n    DomainValidationOptions:\n      is_immutable: true\n      compare:\n        is_ignored: true\n    ExtendedKeyUsages:\n      is_read_only: true\n      from:\n        operation: DescribeCertificate\n        path: Certificate.ExtendedKeyUsages\n    # ... (more fields truncated for display) ..."
    }
  ]
}
```

**🎯 Key Benefits of Ultra-Compact Single-Turn Format:**
- **Token Count**: ~3,000 tokens (well under 32K limit)
- **Focus**: Only 3 key operations vs 100+ in full model  
- **Essential Info**: Service name, protocol, core operations
- **Bedrock Ready**: ✅ Passes all validation requirements
- **Single Turn**: One user message + one assistant response per training example

## 🎯 **Recommended Usage**

### **For Amazon Bedrock Fine-Tuning:**
```bash
# Use ultra-compact generator (stays within token limits)
uv run ultra_compact_generator.py --max-services 50 --output bedrock_compliant.jsonl

# Validate before uploading to Bedrock
uv run bedrock_validation.py bedrock_compliant.jsonl
```

### **For Other Fine-Tuning Platforms:**
```bash
# Use full-model generator for maximum context
uv run full_model_haiku_generator.py --all-services --output full_context_dataset.jsonl
```

## ✅ **Validation Requirements**

Amazon Bedrock requirements (automatically checked by validator):
- **Token Limit**: ≤ 32,000 tokens per example  
- **Format**: Claude 3 Haiku single-turn conversations
- **Line Count**: 32-10,000 training lines, 32-1,000 validation lines
- **File Size**: ≤ 10GB training, ≤ 1GB validation
- **No Reserved Keywords**: `\nHuman:`, `\nAssistant:`

## 📁 **Generated Files**

- `bedrock_compliant_ultra_compact.jsonl` - ✅ Bedrock-validated ultra-compact dataset (148 resources)
- `all_services_full_model_haiku.jsonl` - Full-model dataset with complete context

## 🔧 **Dependencies** 

- `data_extractor.py` - Core extraction logic shared by both generators
- `utils/repo.py` - Repository management utilities
- AWS Controllers repositories (automatically cloned)

## 🚀 **Quick Start**

1. **Generate Bedrock-compliant dataset:**
   ```bash
   uv run ultra_compact_generator.py --max-services 50 --output my_dataset.jsonl
   ```

2. **Validate dataset:**
   ```bash
   uv run bedrock_validation.py my_dataset.jsonl
   ```

3. **Upload to Bedrock for fine-tuning** (if validation passes)

## 📈 **Success Metrics**

- **Ultra-Compact**: 148 resources across 40+ AWS services
- **Validation**: ✅ 100% Bedrock compliant 
- **Format**: Claude 3 Haiku single-turn conversations
- **Size**: 0.5MB (ultra-compact) vs 268MB (full-model)
- **Token Efficiency**: Stays under 32K limit vs 150K+ for full models 