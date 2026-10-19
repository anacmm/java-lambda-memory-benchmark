package benchmark;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class JsonTest {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void requestAndDatasetDeserialize() throws Exception {
        assertEquals(new Models.Request("bucket", "dataset.json"), mapper.readValue(
                "{\"bucket\":\"bucket\",\"key\":\"dataset.json\"}", Models.Request.class));
        var dataset = mapper.readValue(
                "{\"records\":[{\"id\":1,\"value\":7919,\"category\":\"group-1\"}]}", Models.Dataset.class);
        assertEquals(new Models.DataRecord(1, 7919, "group-1"), dataset.records().getFirst());
        var response = new Calculation().process(dataset.records());
        assertEquals(response, mapper.readValue(mapper.writeValueAsBytes(response), Models.Response.class));
    }

    @Test
    void checkedInDatasetHasExpectedResult() throws Exception {
        var dataset = mapper.readValue(Path.of("../sample/dataset.json").toFile(), Models.Dataset.class);
        assertEquals(new Models.Response(4000, "b1e029a3d2d7974c", "OK"),
                new Calculation().process(dataset.records()));
    }
}
