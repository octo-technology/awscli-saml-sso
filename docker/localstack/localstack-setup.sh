echo "Creating AWS S3 bucket $LOCALSTACK_S3_BUCKET_NAME..."
awslocal s3api create-bucket --bucket $LOCALSTACK_S3_BUCKET_NAME

echo "Creating AWS SAML Provider ${LOCALSTACK_SAML_PROVIDER_NAME}..."
awslocal iam create-saml-provider --name ${LOCALSTACK_SAML_PROVIDER_NAME} --saml-metadata-document file:///docker-entrypoint-initaws.d/SAML-Metadata-IDPSSODescriptor.xml

echo "Creating AWS Role.User..."
awslocal iam create-role --role-name Role.User --path / --assume-role-policy-document file:///docker-entrypoint-initaws.d/test-role-trust-relationship-policy.json
awslocal iam put-role-policy --role-name Role.User --policy-name UserPolicy --policy-document file:///docker-entrypoint-initaws.d/test-role-policy.json

echo "Creating AWS Role.Admin..."
awslocal iam create-role --role-name Role.Admin --path / --assume-role-policy-document file:///docker-entrypoint-initaws.d/test-role-trust-relationship-policy.json
awslocal iam put-role-policy --role-name Role.Admin --policy-name AdminPolicy --policy-document file:///docker-entrypoint-initaws.d/test-role-policy.json

echo "... Finished"
