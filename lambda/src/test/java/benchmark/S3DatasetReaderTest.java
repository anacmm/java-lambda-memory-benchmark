package benchmark;

import org.junit.jupiter.api.Test;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class S3DatasetReaderTest {
    @Test
    void forwardsBucketAndKeyAndDownloadsOnEachRead() {
        S3Client client = mock(S3Client.class);
        var request = GetObjectRequest.builder().bucket("test-bucket").key("data.json").build();
        byte[] bytes = {1, 2, 3};
        when(client.getObjectAsBytes(request)).thenReturn(
                ResponseBytes.fromByteArray(GetObjectResponse.builder().contentLength(3L).build(), bytes));
        var reader = new S3DatasetReader(client);
        assertArrayEquals(bytes, reader.read("test-bucket", "data.json"));
        assertArrayEquals(bytes, reader.read("test-bucket", "data.json"));
        verify(client, times(2)).getObjectAsBytes(request);
    }

    @Test
    void rejectsIncompleteObjectOrMissingLength() {
        S3Client client = mock(S3Client.class);
        var request = GetObjectRequest.builder().bucket("test-bucket").key("data.json").build();
        when(client.getObjectAsBytes(request)).thenReturn(
                ResponseBytes.fromByteArray(GetObjectResponse.builder().contentLength(4L).build(), new byte[3]),
                ResponseBytes.fromByteArray(GetObjectResponse.builder().build(), new byte[3]));
        var reader = new S3DatasetReader(client);
        assertThrows(IllegalStateException.class, () -> reader.read("test-bucket", "data.json"));
        assertThrows(IllegalStateException.class, () -> reader.read("test-bucket", "data.json"));
    }

    @Test
    void acceptsCompleteEmptyObject() {
        S3Client client = mock(S3Client.class);
        var request = GetObjectRequest.builder().bucket("test-bucket").key("empty").build();
        when(client.getObjectAsBytes(request)).thenReturn(
                ResponseBytes.fromByteArray(GetObjectResponse.builder().contentLength(0L).build(), new byte[0]));
        assertArrayEquals(new byte[0], new S3DatasetReader(client).read("test-bucket", "empty"));
    }
}
