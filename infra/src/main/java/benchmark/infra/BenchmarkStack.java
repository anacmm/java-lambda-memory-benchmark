package benchmark.infra;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.zip.ZipFile;
import java.io.IOException;
import software.amazon.awscdk.*;
import software.amazon.awscdk.services.lambda.Architecture;
import software.amazon.awscdk.services.lambda.Code;
import software.amazon.awscdk.services.lambda.Function;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.logs.LogGroup;
import software.amazon.awscdk.services.logs.RetentionDays;
import software.amazon.awscdk.services.s3.BlockPublicAccess;
import software.amazon.awscdk.services.s3.Bucket;
import software.amazon.awscdk.services.s3.BucketEncryption;
import software.constructs.Construct;

public class BenchmarkStack extends Stack {
    public BenchmarkStack(Construct scope, String id, StackProps props) {
        super(scope, id, props);
        // cdk.json runs this app from infra/. Refuse accidental deployment of the JVM ZIP.
        Path artifact = Path.of("../lambda/target/function.zip");
        requireNativeArtifact(artifact);
        CfnParameter memory = CfnParameter.Builder.create(this, "MemorySize")
                .type("Number").defaultValue(1024)
                .allowedValues(List.of("256", "512", "1024", "1536", "2048", "3072"))
                .description("Memory in MB; the application artifact stays identical").build();
        Bucket bucket = Bucket.Builder.create(this, "DatasetBucket")
                .blockPublicAccess(BlockPublicAccess.BLOCK_ALL)
                .encryption(BucketEncryption.S3_MANAGED).enforceSsl(true)
                .versioned(false).removalPolicy(RemovalPolicy.DESTROY).build();
        LogGroup logs = LogGroup.Builder.create(this, "BenchmarkLogs")
                .retention(RetentionDays.ONE_WEEK).removalPolicy(RemovalPolicy.DESTROY).build();
        Function function = Function.Builder.create(this, "BenchmarkFunction")
                .runtime(Runtime.PROVIDED_AL2023).architecture(Architecture.ARM_64)
                .handler("bootstrap").code(Code.fromAsset(artifact.toString()))
                .memorySize(memory.getValueAsNumber()).timeout(Duration.seconds(60))
                .logGroup(logs).description("Selectable CPU and S3 I/O workloads for memory benchmarking").build();
        bucket.grantRead(function);
        CfnOutput.Builder.create(this, "BucketName").value(bucket.getBucketName()).build();
        CfnOutput.Builder.create(this, "FunctionName").value(function.getFunctionName()).build();
        CfnOutput.Builder.create(this, "LogGroupName").value(logs.getLogGroupName()).build();
    }

    private static void requireNativeArtifact(Path path) {
        if (!Files.isRegularFile(path)) {
            throw new IllegalStateException("Build the native artifact first: bash scripts/build-native.sh");
        }
        try (ZipFile zip = new ZipFile(path.toFile())) {
            if (zip.getEntry("bootstrap") == null || zip.getEntry("runner") == null
                    || zip.getEntry("cacerts") == null) {
                throw new IllegalStateException("Expected native ZIP with bootstrap, runner, and cacerts");
            }
            try (var input = zip.getInputStream(zip.getEntry("runner"))) {
                byte[] header = input.readNBytes(20);
                // ELF64, little endian, EM_AARCH64 (183).
                if (header.length != 20 || header[0] != 0x7f || header[1] != 'E'
                        || header[2] != 'L' || header[3] != 'F' || header[4] != 2
                        || header[5] != 1 || (header[18] & 0xff) != 183 || header[19] != 0) {
                    throw new IllegalStateException("Native artifact must be Linux ARM64");
                }
            }
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read native Lambda ZIP", e);
        }
    }
}
