package benchmark;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;

@ApplicationScoped
public class S3DatasetReader {
    private final S3Client client;

    @Inject
    public S3DatasetReader(S3Client client) {
        this.client = client;
    }

    public byte[] read(String bucket, String key) {
        // The injected SDK v2 client is reused; the object is downloaded afresh every time.
        var response = client.getObjectAsBytes(GetObjectRequest.builder().bucket(bucket).key(key).build());
        byte[] object = response.asByteArray();
        Long expectedBytes = response.response().contentLength();
        if (expectedBytes == null || expectedBytes != object.length) {
            throw new IllegalStateException("S3 Content-Length does not match received object bytes");
        }
        return object;
    }
}
